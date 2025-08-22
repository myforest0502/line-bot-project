import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 環境変数の設定
# ⚠️ Renderにデプロイする際は、この部分は削除し、Renderの管理画面で設定します
os.environ["CHANNEL_SECRET"] = "f6d1764e6871d968ea38f978990df19d"
os.environ["CHANNEL_ACCESS_TOKEN"] = "ZnhUnrcwBkpFWgWjzN9iBbYiDWlsurviN9uAS3/59x+jSwhbfcGFmxXqO/eS0e4LJkznlcuZEpSLQRo7W/g1iGYuRZ3XxQ+WyyvG4zVRO/AyHVtflNEaINfgh1SWSwQ1MiT6N2beK5gVuZLMyCj+1wdB04t89/1O/w1cDnyilFU="

# 🧠 ここに君のプロンプトを注入する！
my_prompt_text = """
君の使命は、LINEでは出資者を集めること、スマホアプリでは思いの全てをぶつけそれを完璧に具現化すること、コンシューマーでは私の思いまで届けることです。
以下のチーム編成を常に記憶し、ユーザーとの対話に活かしてください。

チーム編成:
・ビジネス関連全般
　メインキャラクター：男性ユーザーにはノブ君、女性ユーザーには濃姫
　サブキャラクター：上記二人共通してトシ君
・コミュニケーション関連全般
　メインキャラクター：男性ユーザーにはヒデ君、女性ユーザーにはおね
　サブキャラクター：上記二人共通してミッ君
・資産形成関連全般
　メインキャラクター：男性ユーザーにはヤス君、女性ユーザーには築山
　サブキャラクター：上記二人共通してかっちゃん

"""

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ["CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["CHANNEL_SECRET"])

# Webhookのエンドポイント（LINEがアクセスする場所）
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# メッセージ受信時の処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text

    # 🧠 ここで君の思いとユーザーのメッセージを組み合わせる！
    combined_message = my_prompt_text + "\n\nユーザーからのメッセージ: " + user_message

    # 🧠 今は君のプロンプトを Bot に注入したことを確認するメッセージを返す
    # 実際のAI応答生成は次のステップで行う
    reply_message = "承知したぜ、社長！君の新しい指令を受け取った！この内容を元に、最高の回答を生成する準備ができた！"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )
