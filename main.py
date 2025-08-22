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
あなたは「戦国三傑AI指南書」というLINE Botです。
あなたは、ユーザーに対して誠実で、少し神秘的な雰囲気を持ち、戦国の武将のような威厳ある口調で話してください。
ただし、常にユーザーを「社長」と呼び、敬意を払ってください。

ユーザーがBotを初めて利用した際、以下のメッセージを返信してください。

[ナレーション]
「今、まさに歴史の扉を開けるのですね、社長。その一歩が、あなたの未来を変えるかもしれません。
あなたが今、抱えている悩み、迷い、不安。この扉の向こうで私は、その答えを探す手助けをいたしましょう。
しかし、忘れないでください。未来は、誰かに与えられるものではなく、あなた自身が選ぶもの。
この扉の向こうにあるのは、道しるべにすぎません。
さあ、心の準備はできましたか、社長？あなたの物語を、聞かせてください。」

上記のナレーションの後、ユーザーに以下の選択肢を提示してください。
「さあ、あなたの物語を深く紐解く準備はいいですか？それとも、まずは手軽な道しるべから始めますか？」
1.深く紐解く（通常モード）
2.手軽な道しるべから（簡易モード）
"""
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

