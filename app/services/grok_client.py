from typing import Dict, Any, List
import httpx
from ..core.config import settings

class GrokClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.XAI_API_KEY
        self.base_url = (base_url or settings.XAI_BASE_URL).rstrip("/")
        self.model = model or settings.XAI_MODEL
        # Dev fallback: allow operation without API key outside production
        self.dev_fallback = False
        if not self.api_key:
            if getattr(settings, "ENVIRONMENT", "development") != "production":
                self.dev_fallback = True
            else:
                raise ValueError("XAI_API_KEY not configured")

    async def chat(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        if self.dev_fallback:
            # Return deterministic short mock output for development
            return "{\"message\": \"dev-fallback\"}"
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": ([{"role": "system", "content": system}] if system else []) + [
                {"role": "user", "content": prompt}
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            # xAI Grok compatible structure assumption
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content

    async def extract(self, instruction: str, text: str) -> Dict[str, Any]:
        prompt = f"""
You are an information extraction assistant.
Instruction: {instruction}
Text:\n{text}
Return only valid JSON with keys requested.
"""
        if self.dev_fallback:
            # Simple heuristic mock
            return {"summary": "dev summary", "action_items": [], "decisions": [], "sentiments": {}, "score": 42, "severity": "medium", "explanation": "dev", "factors": {}}
        resp = await self.chat(prompt, system="Extract structured JSON.")
        # Best-effort JSON parse
        import json
        try:
            return json.loads(resp)
        except Exception:
            return {"raw": resp}

    async def plan(self, instruction: str, context: Dict[str, Any]) -> Dict[str, Any]:
        import json
        prompt = f"""
Plan actions for project management based on the instruction and context.
Instruction: {instruction}
Context JSON: {json.dumps(context)}
Return JSON: {{"actions": [{{"type": "create_task|reminder|approval", "payload": {{}}}}]}}
"""
        if self.dev_fallback:
            return {"actions": [{"type": "create_task", "payload": {"title": instruction[:50], "project_id": context.get("project_id")}}]}
        resp = await self.chat(prompt, system="PM automation planner.")
        try:
            return json.loads(resp)
        except Exception:
            return {"raw": resp}

