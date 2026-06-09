"""
Natural language → structured transaction parser via local Ollama.
"""
import json
import re
import requests
from datetime import date, datetime, timedelta

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:7b"   # 改成你本地装的模型名

SYSTEM_PROMPT = """你是一个记账助手。用户会用一句话描述一笔收支，你需要解析成 JSON。

返回格式（严格 JSON，不要 markdown）：
{
  "amount": 数字,
  "date": "YYYY-MM-DD",
  "type": "expense" 或 "income",
  "category": "分类名",
  "subcategory": "子分类名（可选）",
  "project": "项目名（可选）",
  "note": "备注摘要"
}

分类对照表（category 必须是以下之一）：
支出: 餐饮, 交通, 购物, 娱乐, 居住, 医疗, 教育, 通讯, 其他支出
收入: 工资, 奖金, 投资, 兼职, 其他收入

子分类参考：
餐饮: 早餐, 午餐, 晚餐, 零食, 饮品, 外卖
交通: 公交, 地铁, 打车, 加油, 停车
购物: 日用品, 服饰, 数码, 家居
娱乐: 电影, 游戏, 会员, 旅行
居住: 房租, 水电, 物业, 维修
医疗: 药品, 挂号, 体检
教育: 课程, 书籍, 培训
通讯: 话费, 宽网
其他支出: 材料, 耗材, 其他

规则：
1. 金额必须是正数
2. 日期：今天=当天，昨天=前一天，前天=前两天，周几=最近的那天。没提就默认今天
3. 分类不确定时选"其他支出"或"其他收入"
4. 如果一句话描述了多笔交易，只解析第一笔
5. 只返回 JSON，不要其他文字"""


def parse_natural_language(text: str, model: str = DEFAULT_MODEL) -> dict:
    """Call Ollama to parse a natural language description into structured data."""

    today_str = date.today().isoformat()
    prompt = f"[今天日期: {today_str}]\n用户输入: {text}"

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
    except requests.ConnectionError:
        return _fallback_parse(text)
    except Exception:
        return _fallback_parse(text)

    # Try to extract JSON from response
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            parsed = json.loads(match.group())
        else:
            return _fallback_parse(text)

    return _validate(parsed, text)


def _validate(parsed: dict, original: str) -> dict:
    """Validate and normalize parsed result, flag missing fields."""
    today = date.today().isoformat()

    result = {
        "amount": None,
        "date": today,
        "type": "expense",
        "category": "其他支出",
        "subcategory": None,
        "project": None,
        "note": original,
        "needs_confirmation": False,
        "missing_fields": [],
    }

    # Amount
    if parsed.get("amount") and float(parsed["amount"]) > 0:
        result["amount"] = round(float(parsed["amount"]), 2)
    else:
        result["needs_confirmation"] = True
        result["missing_fields"].append("amount")

    # Date
    if parsed.get("date"):
        try:
            datetime.strptime(parsed["date"], "%Y-%m-%d")
            result["date"] = parsed["date"]
        except ValueError:
            result["needs_confirmation"] = True
            result["missing_fields"].append("date")

    # Type
    if parsed.get("type") in ("income", "expense"):
        result["type"] = parsed["type"]

    # Category
    valid_expense = ["餐饮","交通","购物","娱乐","居住","医疗","教育","通讯","其他支出"]
    valid_income = ["工资","奖金","投资","兼职","其他收入"]
    cat = parsed.get("category", "")
    if cat in valid_expense or cat in valid_income:
        result["category"] = cat
    else:
        # Try fuzzy match
        all_cats = valid_expense + valid_income
        for c in all_cats:
            if cat and c in cat:
                result["category"] = c
                break

    # Ensure category matches type
    if result["type"] == "expense" and result["category"] not in valid_expense:
        result["category"] = "其他支出"
    if result["type"] == "income" and result["category"] not in valid_income:
        result["category"] = "其他收入"

    result["subcategory"] = parsed.get("subcategory")
    result["project"] = parsed.get("project")
    result["note"] = parsed.get("note") or original

    # Double check critical fields
    if result["amount"] is None:
        result["needs_confirmation"] = True
        if "amount" not in result["missing_fields"]:
            result["missing_fields"].append("amount")

    return result


def _fallback_parse(text: str) -> dict:
    """Regex-based fallback when Ollama is unavailable."""
    today = date.today().isoformat()

    # Extract amount: look for numbers
    amount = None
    nums = re.findall(r'(\d+\.?\d*)', text)
    if nums:
        amount = round(float(nums[0]), 2)

    # Date keywords
    date_str = today
    if "昨天" in text:
        date_str = (date.today() - timedelta(days=1)).isoformat()
    elif "前天" in text:
        date_str = (date.today() - timedelta(days=2)).isoformat()

    # Type
    income_kw = ["工资","奖金","收入","报销","到账","赚了","入账"]
    tx_type = "income" if any(k in text for k in income_kw) else "expense"

    # Simple category detection (only for expense)
    cat = "其他支出" if tx_type == "expense" else "其他收入"
    if tx_type == "expense":
        # Order matters: more specific keywords first
        cat_map = [
            ("餐饮", ["吃","饭","餐","面","粉","奶茶","咖啡","外卖","午餐","晚餐","早餐","零食","烧烤","火锅"]),
            ("交通", ["打车","公交","地铁","滴滴","油费","停车","高速"]),
            ("医疗", ["药","医院","挂号","看病","体检"]),
            ("教育", ["课程","培训","学费","书","买书","教材","课"]),
            ("居住", ["房租","水电","物业","装修"]),
            ("娱乐", ["电影","游戏","KTV","唱歌","旅游"]),
            ("通讯", ["话费","流量","宽带","网费"]),
            ("其他支出", ["耗材","材料","配件","维修"]),
            ("购物", ["淘宝","京东","超市","商场","网购","衣服","鞋","包"]),
        ]
        for c, keywords in cat_map:
            if any(k in text for k in keywords):
                cat = c
                break

    needs = amount is None
    missing = ["amount"] if needs else []

    return {
        "amount": amount,
        "date": date_str,
        "type": tx_type,
        "category": cat,
        "subcategory": None,
        "project": None,
        "note": text,
        "needs_confirmation": needs,
        "missing_fields": missing,
    }
