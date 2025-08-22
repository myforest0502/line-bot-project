import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 環境変数の設定
# ⚠️ Renderにデプロイする際は、この部分は削除し、Renderの管理画面で設定します


# 🧠 ここに君のプロンプトを注入する！
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
)



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
@app.route('/health')
def health():
    return "OK", 200
@app.route("/", methods=["GET"])
def index():
    return "LINE Bot is running, 社長！"










