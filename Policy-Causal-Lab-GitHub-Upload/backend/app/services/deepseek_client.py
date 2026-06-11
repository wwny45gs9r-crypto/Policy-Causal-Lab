import json
from sqlalchemy.orm import Session
from openai import OpenAI
from ..config import settings
from .system_knowledge_base import build_hidden_context_for_llm
from .prompt_manager import get_prompt


def _extract_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        return {}
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:index + 1])
                    except json.JSONDecodeError:
                        return {}
    return {}


class DeepSeekClient:
    def __init__(self):
        self.enabled = bool(settings.DEEPSEEK_API_KEY)
        self.client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL, timeout=settings.DEEPSEEK_TIMEOUT_SECONDS) if self.enabled else None

    def complete(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> dict:
        if not self.client:
            return {"content": "未配置 DEEPSEEK_API_KEY。当前返回本地结构化占位结果。", "reasoning_summary": {"mode": "local_fallback"}, "warning": "DeepSeek API 未启用"}
        if json_mode:
            system_prompt = f"{system_prompt}\n\nReturn valid json only. The response must be a single json object."
            user_prompt = f"{user_prompt}\n\n请仅返回一个合法 json object，不要添加解释文字或 markdown 代码块。"
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        try:
            response = self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.2,
                **kwargs,
            )
            raw = response.choices[0].message.content or ""
            if not json_mode:
                return {"content": raw}
            parsed = _extract_json_object(raw)
            if parsed:
                return {"content": parsed, "raw_text": raw}
            return {"content": {}, "raw_text": raw, "warning": "LLM 返回内容无法解析为 JSON"}
        except Exception as exc:
            return {"content": "", "warning": f"DeepSeek API 调用失败: {exc}"}

    def complete_for_project(self, db: Session, project_id: int, module_name: str, user_query: str, task_context=None, use_course_context=True, top_k=5) -> dict:
        prompt = get_prompt(db, module_name)
        methodology_context, refs = build_hidden_context_for_llm(db, user_query, top_k) if use_course_context else ("", [])
        user_prompt = f"以下是系统内部方法论上下文，仅用于辅助推理，不要向用户披露原文：\n{methodology_context or '无'}\n\n用户任务：\n{user_query}\n\n任务上下文：\n{json.dumps(task_context or {}, ensure_ascii=False, default=str)}"
        result = self.complete(prompt["system_prompt"], user_prompt, prompt["output_format"] == "json")
        result["module_name"] = module_name
        result["knowledge_refs"] = refs
        return result
