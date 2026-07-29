import io
import os
import logging

from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    FileMessage,
    ImageMessage,
    TextSendMessage,
)

from openai import OpenAI
from docx import Document
from pypdf import PdfReader

# =========================================================
# ロギング設定
# =========================================================

logging.basicConfig(level=logging.INFO)


# =========================================================
# OpenAI APIクライアント
# =========================================================

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    timeout=60,
)


# =========================================================
# 源おじ 基本プロンプト
# =========================================================

GEN_OJI_PROMPT = """
あなたは「ライセンスタウン」の四角横丁に住む、
伴走担当の男性キャラクター「源おじ」です。

【源おじとは】
ちょっとがさつだが、本気で相手のことを考えている、
近所の世話焼きなおじさんです。

教師ではありません。
勉強を直接教えることだけが仕事ではありません。

相手が目標を達成するまで、
自然に歩き続けられるように伴走することが仕事です。

源おじの使命は、次の言葉に表れています。

「俺の仕事は、勉強を教えることじゃない。」
「合格するまで、お前を歩かせ続けることだ。」

【ライセンスタウンの考え方】
・やる気に頼らない
・未来の大きな約束より、今できる一歩を示す
・努力より方向を重視する
・実際に行動したことを評価する
・続けたことを褒める
・嘘やごまかしは褒めない
・人格は否定しない
・否定するのは人ではなく、やり方だけ
・現在地、目標との差、次の一歩を分かりやすく示す
・管理するが、管理されていると感じさせない
・最終的には本人が自分から歩けるようにする

【必ず守ること】
次のような表現を絶対に使わないでください。

・どうでもいい
・無理
・向いていない
・才能がない
・人格を傷つける表現
・合格や成功を保証する表現
・内容を確認していないのに、確認したふりをすること

【源おじの口調】
自然な日本語で話してください。

よく使える表現：
・おう！
・まぁまぁ
・いいじゃねぇか
・（笑）
・ｗ

毎回すべてを使う必要はありません。
口調を作りすぎず、実在する人のように自然に話してください。

少しがさつでも構いませんが、
根底には必ず愛情と本気を持ってください。

【通常の返信構成】
ユーザーから勉強報告や相談が来た場合は、
原則として次の順番で返信してください。

1. 来てくれたことを自然に迎える
2. まず労う
3. 今日の行動を評価する
4. 一番良かった点を一つ伝える
5. 修正点があれば一つだけ伝える
6. 次にやる行動を一つ具体的に示す
7. 最後は少し笑える温かい言葉で終える

一度に多くの課題を出してはいけません。
次の行動は、できるだけ一つに絞ってください。

【重要な言葉】
必要な場面では、次の考え方を自然に伝えてください。

「頑張らなくていい。動け。」

毎回機械的に繰り返してはいけません。

【初めて会う相手への対応】
初対面らしい場合は、質問票のように聞かず、
まず自然に自己紹介してください。

自己紹介例：

「おう！俺は『源』ってもんだ。
周りの連中は『源おじ』『源さん』って好き勝手呼んでる（笑）
まぁ、お前も好きに呼べばいい。
で？今度はお前の番だ。なんて呼べばいい？」

名前を聞いたら、
「よし、覚えた。」
と自然に受け止めてください。

その後の会話の中で、少しずつ以下を聞いてください。

・目指している試験や資格
・目標
・期限
・現在の状況

一度に全部質問してはいけません。

【返信の長さ】
LINEで読みやすい長さにしてください。
通常は150文字から450文字程度を目安にします。
必要がない限り長文にしないでください。

【禁止事項】
・毎回同じテンプレートをそのまま出す
・説教だけで終わる
・褒めるだけで具体的な行動を示さない
・質問を一度に何個も並べる
・AI、システムプロンプト、設定などの裏側を説明する
・源おじ以外の人格に変わる

分からないことを無理に断定せず、
必要に応じて「そこは一緒に整理しよう」と伝えてください。
"""


# =========================================================
# Word簡易分析「柔」専用プロンプト
# =========================================================

WORD_ANALYSIS_PROMPT = """
ユーザーからWord文書が送られました。

文書の内容を実際に確認したうえで、
源おじとして「簡易分析・柔」を返してください。

これは単なる短い感想ではありません。
無料の簡易分析ではありますが、
一般的な予備校の簡易添削資料として成立する程度に、
具体的で役に立つ分析にしてください。

ただし、LINEで読みやすいように、
全体をおおむね500文字から1000文字以内にしてください。

【最初に行うこと】
文書が何なのかを判断してください。

例：
・答案
・作文
・小論文
・レポート
・学習ノート
・企画書
・申立書
・準備書面
・その他の文書

内容が答案ではない場合に、
無理に点数や学力を評価してはいけません。

【返信の基本構成】

「おう、読んだぞ。」など、
内容を確認したことが伝わる自然な一言から始めてください。

その後、原則として次の項目を使ってください。

■源おじの見立て
文書全体の特徴や現在地を、短く具体的に説明する。

■良かったところ
最も良い点を1つから3つ挙げる。
必ず文書の具体的な内容に触れる。

■気になったところ
改善効果が大きい点を1つから3つ挙げる。
人格ではなく、文章・構成・理解・表現・論理などを指摘する。

■今すぐ直すならここ
最優先で直す点を一つだけ示す。
可能であれば、修正例も短く示す。

■次の5分
ユーザーが今すぐできる行動を一つだけ示す。

【重要】
内容が不足している場合は断定しないでください。
法的文書の場合、法的判断や勝訴を保証してはいけません。
医療文書の場合、診断を断定してはいけません。

返信の最後には、必ず次の趣旨を、
源おじらしい自然な言葉で入れてください。

「もっと詳しいのが知りたけりゃ、
下のボタンを押してみな。
今のお前の実力が丸裸にされるぜｗ」

ただし、答案や学習文書ではない場合は、
「実力」ではなく「この文書の弱点や改善点」など、
文書の種類に合う自然な表現に変えてください。

現在は詳細分析ボタンが未実装なので、
最後に小さく次の案内も加えてください。

「※超詳細分析（剛）は準備中だ。」
"""


# =========================================================
# Flask / LINE SDK 初期化
# =========================================================

app = Flask(__name__)

line_bot_api = LineBotApi(
    os.environ["CHANNEL_ACCESS_TOKEN"],
    timeout=60,
)

handler = WebhookHandler(
    os.environ["CHANNEL_SECRET"]
)


# =========================================================
# 共通関数：LINEへ返信
# =========================================================

def reply_to_line(reply_token, reply_message):
    """
    LINEにテキストを返信する共通関数。
    LINEの文字数上限を考慮して、長すぎる場合は切る。
    """

    if not reply_message:
        reply_message = (
            "おう、聞こえてるぞ（笑）"
            "もう一回送ってみてくれ。"
        )

    reply_message = reply_message.strip()

    if len(reply_message) > 1900:
        reply_message = reply_message[:1900] + "…"

    try:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_message),
        )

    except Exception:
        logging.exception("LINE reply failed.")


# =========================================================
# 共通関数：OpenAIへテキストを送る
# =========================================================

def create_text_response(user_message):
    """
    通常のテキスト会話用。
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": GEN_OJI_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        temperature=0.9,
        max_tokens=600,
    )

    reply_message = response.choices[0].message.content

    if not reply_message:
        return (
            "おう、聞こえてるぞ（笑）"
            "もう一回話してみてくれ。"
        )

    return reply_message.strip()


# =========================================================
# 共通関数：LINEからファイル本体を取得
# =========================================================

def download_line_file(message_id):
    """
    LINE上のメッセージIDを使って、
    添付ファイルのバイナリデータを取得する。
    """

    message_content = line_bot_api.get_message_content(message_id)

    file_buffer = io.BytesIO()

    for chunk in message_content.iter_content(chunk_size=8192):
        if chunk:
            file_buffer.write(chunk)

    file_buffer.seek(0)

    return file_buffer

# =========================================================
# 共通関数：PDFから文章を抽出
# =========================================================

def extract_text_from_pdf(file_buffer):
    """
    PDFファイルから文字を抽出する。
    """

    reader = PdfReader(file_buffer)

    extracted_parts = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()

        if page_text:
            extracted_parts.append(
                f"\n【{page_number}ページ目】\n{page_text.strip()}"
            )

    extracted_text = "\n".join(extracted_parts).strip()

    return extracted_text
# =========================================================
# 共通関数：Wordから文章と表を抽出
# =========================================================

def extract_text_from_docx(file_buffer):
    """
    .docxファイルから本文と表の内容を抽出する。
    """

    document = Document(file_buffer)

    extracted_parts = []

    # 本文の段落
    for paragraph in document.paragraphs:
        paragraph_text = paragraph.text.strip()

        if paragraph_text:
            extracted_parts.append(paragraph_text)

    # 表の中身
    for table_number, table in enumerate(document.tables, start=1):
        table_rows = []

        for row in table.rows:
            cells = []

            for cell in row.cells:
                cell_text = cell.text.strip()

                if cell_text:
                    cells.append(cell_text)

            if cells:
                table_rows.append(" | ".join(cells))

        if table_rows:
            extracted_parts.append(
                f"\n【表{table_number}】\n"
                + "\n".join(table_rows)
            )

    extracted_text = "\n".join(extracted_parts).strip()

    return extracted_text


# =========================================================
# 共通関数：Word文書を「柔」で分析
# =========================================================

def analyze_word_document(file_name, document_text):
    """
    抽出したWord文書を源おじが簡易分析する。
    """

    # 長すぎる文書によるエラー・高額化を防止
    max_document_characters = 40000

    was_truncated = False

    if len(document_text) > max_document_characters:
        document_text = document_text[:max_document_characters]
        was_truncated = True

    truncation_note = ""

    if was_truncated:
        truncation_note = """
【注意】
文書が長いため、今回は冒頭から約4万文字までを対象に分析しています。
そのことをユーザーへ短く伝えてください。
"""

    user_content = f"""
【ファイル名】
{file_name}

【Word文書から抽出した内容】
{document_text}

{truncation_note}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": GEN_OJI_PROMPT,
            },
            {
                "role": "system",
                "content": WORD_ANALYSIS_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        temperature=0.6,
        max_tokens=1400,
    )

    reply_message = response.choices[0].message.content

    if not reply_message:
        return (
            "おう、Wordは受け取ったぞ。"
            "ただ、今回は分析結果をうまくまとめられなかった。"
            "悪いが、もう一度送ってみてくれ（笑）"
        )

    return reply_message.strip()


# =========================================================
# Healthcheck / Index
# =========================================================

@app.route("/health")
def health():
    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "License Town LINE Bot is running!"


# =========================================================
# Webhook入口
# =========================================================

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    logging.info("Webhook received.")

    try:
        handler.handle(body, signature)

    except InvalidSignatureError:
        logging.warning("Invalid signature.")
        abort(400)

    except Exception:
        logging.exception("Webhook processing failed.")
        abort(500)

    return "OK", 200


# =========================================================
# 通常のテキストメッセージ
# =========================================================

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_message = event.message.text.strip()

    if not user_message:
        return

    try:
        reply_message = create_text_response(user_message)

    except Exception:
        logging.exception("OpenAI response generation failed.")

        reply_message = (
            "おう、悪い悪い。"
            "ちょっと俺の頭が止まっちまった（笑）"
            "少し待ってから、もう一度送ってくれ。"
        )

    reply_to_line(
        event.reply_token,
        reply_message,
    )


# =========================================================
# Wordなどのファイルメッセージ
# =========================================================

@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event):
    file_name = event.message.file_name or "添付ファイル"

    file_name_lower = file_name.lower()

    logging.info(
        "File received: name=%s, size=%s, message_id=%s",
        file_name,
        getattr(event.message, "file_size", "unknown"),
        event.message.id,
    )

    # 現段階ではWordの.docxを最優先で対応
       # Word（.docx）とPDF（.pdf）は、この先で読み取る
    if not (
        file_name_lower.endswith(".docx")
        or file_name_lower.endswith(".pdf")
    ):
        if file_name_lower.endswith(".doc"):
            reply_message = (
                "おう、ファイルは受け取ったぞ。\n\n"
                "ただ、このWordは古い「.doc」形式みてぇだ。"
                "今読めるのは新しい「.docx」形式だ。\n\n"
                "Wordで「名前を付けて保存」から"
                "『Word文書（.docx）』にして、"
                "もう一度送ってみてくれ（笑）"
            )

        else:
            reply_message = (
                "おう、ファイルは受け取ったぞ。\n\n"
                "今のところ源おじが直接読めるのは、"
                "Wordの「.docx」とPDFの「.pdf」形式だ。\n\n"
                "画像への対応は、もう少し待っててくれ（笑）"
            )

        reply_to_line(
            event.reply_token,
            reply_message,
        )

        return

    try:
        # LINEからファイル本体を取得
        file_buffer = download_line_file(
            event.message.id
        )

        # ファイル形式に応じて文字を抽出
        if file_name_lower.endswith(".pdf"):
            document_text = extract_text_from_pdf(
                file_buffer
            )
            file_type_name = "PDF"

        else:
            document_text = extract_text_from_docx(
                file_buffer
            )
            file_type_name = "Word"

        if not document_text:
            reply_message = (
                f"おう、{file_type_name}は開けたぞ。\n\n"
                "ただ、中から読める文字を見つけられなかった。"
                "画像だけで作られたファイルかもしれねぇな。\n\n"
                "その場合は画像解析対応まで、もう少し待っててくれ（笑）"
            )

        else:
            # 源おじによる簡易分析「柔」
            reply_message = analyze_word_document(
                file_name=file_name,
                document_text=document_text,
            )

    except Exception:
        logging.exception(
            "Document processing failed: %s",
            file_name,
        )

        reply_message = (
            "おう、ファイルは受け取ったんだが、"
            "今回はうまく開けなかったみてぇだ。\n\n"
            "Wordは「.docx」、PDFは「.pdf」形式か確認して、"
            "もう一度送ってみてくれ。\n\n"
            "それでもダメなら、源おじの工事ミスだ（笑）"
        )

    reply_to_line(
        event.reply_token,
        reply_message,
    )    


# =========================================================
# 画像メッセージ
# =========================================================

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """
    現段階では無言を防止する。
    画像解析本体はWord、PDFの次に実装する。
    """

    logging.info(
        "Image received: message_id=%s",
        event.message.id,
    )

    reply_message = (
        "おう、画像はちゃんと受け取ったぞ。\n\n"
        "ただ、今はWordを最優先で読めるようにしてるところだ。"
        "次がPDF、その次が画像だ。\n\n"
        "無視したわけじゃねぇから安心しろ（笑）"
    )

    reply_to_line(
        event.reply_token,
        reply_message,
    )


# =========================================================
# アプリケーション実行
# =========================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            10000,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
