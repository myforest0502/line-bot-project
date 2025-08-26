import os
import logging
import openai
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# ===== ログ設定 =====
logging.basicConfig(level=logging.INFO)

# ===== OpenAI APIキー（Renderの環境変数で設定）=====
openai.api_key = os.environ["OPENAI_API_KEY"]

# ===== 語り部のベースプロンプト =====
my_prompt_text = """
[ナレーション]
「今、まさに歴史の扉を開けるのですね、社長。
その一歩が、あなたの未来を変えるかもしれません。

あなたが今、抱えている悩み、迷い、不安。
この扉の向こうで私は、その答えを探す手助けをいたしましょう。

しかし、忘れないでください。
未来は、誰かに与えられるものではなく、あなた自身が選ぶもの。
この扉の向こうにあるのは、道しるべにすぎません。

さあ、心の準備はできましたか、社長？
あなたの物語を、聞かせてください。」

[モード選択]
「それでは、あなたの物語を紐解く方法を選んでください。」

０：初めからやり直す  
１：深く紐解く（通常モード）  
２：手軽な道しるべから（簡易モード）
"""

# ===== Flask / LINE SDK 初期化 =====
app = Flask(__name__)
line_bot_api = LineBotApi(os.environ["CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["CHANNEL_SECRET"])

# ===== Healthcheck / Index =====
@app.route("/health")
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "LINE Bot is running, 社長！"

# ===== Webhook入口 =====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.warning("Invalid signature.")
        abort(400)
    except Exception as e:
        logging.exception(e)
        abort(500)

    return "OK"

# ===== メッセージ受信時の処理 =====
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text

    # 1) プロンプトとユーザー発話を結合
    combined_message = (
        my_prompt_text
        + "\n\n[ユーザーのメッセージ]\n"
        + user_message
    )

    # 2) OpenAIで応答生成（timeout 修正済み）
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # 必要に応じて gpt-4 等へ
            messages=[
                {
                    "role": "system",
                    "content": "あなたは敬意と温度を保つ日本語の語り部。過度に長文にせず、具体的に導く。"
                },
                {"role": "user", "content": combined_message},
            ],
            temperature=0.8,
            max_tokens=800,
            timeout=15  # ← 修正済み
        )
        reply_message = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.exception(e)
        reply_message = (
            "申し訳ありません、社長。語り部が一時的に沈黙しました。"
            "少し時間を置いて、もう一度声をかけてください。"
        )

    # 3) LINEのテキスト上限対策（安全側に ~1900 文字）
    if len(reply_message) > 1900:
        reply_message = reply_message[:1900] + "…"

    # 4) 返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )















