import json
import time
import requests


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_articles():
    with open("articles.json", "r", encoding="utf-8") as f:
        return json.load(f)


def create_article(base_url: str, headers: dict, cookie_str: str, article: dict):
    post_headers = headers.copy()
    post_headers["Cookie"] = cookie_str

    resp = requests.post(
        url=base_url,
        headers=post_headers,
        json=article,
        timeout=25
    )
    print(f"HTTP状态码: {resp.status_code}")
    try:
        res_json = resp.json()
        print(json.dumps(res_json, ensure_ascii=False, indent=2))
        return res_json
    except Exception as e:
        print(f"❗JSON解析失败, error:{e}, raw响应:\n{resp.text}")
        return None


def main():
    cfg = load_config()
    article_list = load_articles()
    total = len(article_list)
    interval = cfg["request_interval"]
    print(f"====批量发布启动，共 {total} 篇稿件====")

    for idx, article in enumerate(article_list, start=1):
        print(f"\n【{idx}/{total}】标题：{article['title']}")
        create_article(
            base_url=cfg["base_url"],
            headers=cfg["headers"],
            cookie_str=cfg["cookie"],
            article=article
        )
        if idx != total:
            print(f"等待 {interval}s ...")
            time.sleep(interval)

    print("\n====全部任务执行结束====")


if __name__ == "__main__":
    main()
