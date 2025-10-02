"""
Tenant management service for organization database provisioning
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.tenant_manager import tenant_manager
from ..models.master.organization import Organization
from ..models.master.user import User


class TenantService:
    """Service for managing tenant databases and organizations"""
    
    @staticmethod
    async def create_organization_with_database(
        organization_data: dict,
        admin_user_data: dict,
        master_db: AsyncSession
    ) -> tuple[Organization, User]:
        """Create a new organization and its dedicated database"""
        
        try:
            # Create organization in master database
            organization = Organization(**organization_data)
            master_db.add(organization)
            await master_db.flush()  # Get the organization ID
            
            # Create tenant database
            success = await tenant_manager.create_tenant_database(organization.id)
            if not success:
                raise Exception("Failed to create tenant database")
            
            # Update organization to mark database as created
            organization.database_created = True
            organization.database_name = f"zphere_tenant_{organization.id}"
            
            # Create admin user in master database
            admin_user_data["organization_id"] = organization.id
            admin_user = User(**admin_user_data)
            master_db.add(admin_user)
            
            await master_db.commit()
            
            return organization, admin_user
            
        except Exception as e:
            await master_db.rollback()
            # Cleanup: try to delete the tenant database if it was created
            if organization and organization.id:
                await tenant_manager.delete_tenant_database(organization.id)
            raise e
    
    @staticmethod
    async def delete_organization_and_database(
        organization_id: str,
        master_db: AsyncSession
    ) -> bool:
        """Delete organization and its tenant database (DANGEROUS!)"""
        
        try:
            # Get organization
            result = await master_db.execute(
                select(Organization).where(Organization.id == organization_id)
            )
            organization = result.scalar_one_or_none()
            
            if not organization:
                return False
            
            # Delete all users in the organization
            await master_db.execute(
                select(User).where(User.organization_id == organization_id)
            )
            users_result = await master_db.execute(
                select(User).where(User.organization_id == organization_id)
            )
            users = users_result.scalars().all()
            
            for user in users:
                await master_db.delete(user)
            
            # Delete organization
            await master_db.delete(organization)
            await master_db.commit()
            
            # Delete tenant database
            await tenant_manager.delete_tenant_database(organization_id)
            
            return True
            
        except Exception as e:
            await master_db.rollback()
            print(f"Error deleting organization {organization_id}: {e}")
            return False
    
    @staticmethod
    async def ensure_tenant_database_exists(
        organization: Organization,
        master_db: AsyncSession
    ) -> bool:
        """Ensure tenant database exists for organization"""
        
        if organization.database_created:
            return True
        
        try:
            # Create tenant database
            success = await tenant_manager.create_tenant_database(organization.id)
            
            if success:
                # Update organization record
                organization.database_created = True
                organization.database_name = f"zphere_tenant_{organization.id}"
                master_db.add(organization)
                await master_db.commit()
                return True
            
            return False
            
        except Exception as e:
            await master_db.rollback()
            print(f"Error ensuring tenant database for {organization.id}: {e}")
            return False
    
    @staticmethod
    async def get_organization_stats(
        organization_id: str
    ) -> dict:
        """Get statistics for an organization from its tenant database"""
        
        try:
            # Get tenant database session
            tenant_session = await tenant_manager.get_tenant_session(organization_id)
            
            # Import tenant models dynamically to avoid circular imports
            from ..models.tenant.project import Project
            from ..models.tenant.customer import Customer
            
            try:
                # Count projects
                projects_result = await tenant_session.execute(
                    select(Project).where(Project.is_archived == False)
                )
                active_projects = len(projects_result.scalars().all())
                
                # Count customers
                customers_result = await tenant_session.execute(
                    select(Customer).where(Customer.is_active == True)
                )
                active_customers = len(customers_result.scalars().all())
                
                return {
                    "active_projects": active_projects,
                    "active_customers": active_customers,
                    "database_name": f"zphere_tenant_{organization_id}"
                }
                
            finally:
                await tenant_session.close()
                
        except Exception as e:
            print(f"Error getting stats for organization {organization_id}: {e}")
            return {
                "active_projects": 0,
                "active_customers": 0,
                "error": str(e)
            }
