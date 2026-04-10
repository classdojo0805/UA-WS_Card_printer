import os
import io
import re
import time
import requests
from math import floor
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, send_file, jsonify
from queue import Queue  
from flask import Response 
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import zipfile

app = Flask(__name__)

log_queues = {}

def send_log(session_id, message):
    """輔助函式：將訊息放入對應的佇列"""
    if session_id and session_id in log_queues:
        log_queues[session_id].put(message)
    print(f"[{session_id}] {message}") # 同時印在後台

# --- 參數設定 ---
A4_WIDTH_CM = 21.0
A4_HEIGHT_CM = 29.7
DPI = 300
CARD_WIDTH_CM = 6.47
CARD_HEIGHT_CM = 9.02

A4_WIDTH_PX = int(A4_WIDTH_CM / 2.54 * DPI)
A4_HEIGHT_PX = int(A4_HEIGHT_CM / 2.54 * DPI)
CARD_WIDTH_PX = int(CARD_WIDTH_CM / 2.54 * DPI)
CARD_HEIGHT_PX = int(CARD_HEIGHT_CM / 2.54 * DPI)

COLS = floor(A4_WIDTH_PX / CARD_WIDTH_PX)
ROWS = floor(A4_HEIGHT_PX / CARD_HEIGHT_PX)
CARDS_PER_PAGE = COLS * ROWS

def get_driver():
    options = Options()
    #options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    zoom_out = "--force-device-scale-factor=0.5"
    options.add_argument(zoom_out)
    return webdriver.Chrome(service=service, options=options)

# --- 多執行緒下載 ---
def download_single_image(url):
    """
    下載單張圖片並回傳 PIL Image 物件 (記憶體運作，不存檔)
    """
    if not url or "dummy.gif" in url:
        return Image.new("RGB", (CARD_WIDTH_PX, CARD_HEIGHT_PX), "white")
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            image_data = io.BytesIO(response.content)
            return Image.open(image_data).convert("RGB")
    except Exception as e:
        print(f"圖片下載失敗: {url} | 錯誤: {e}")
    
    return Image.new("RGB", (CARD_WIDTH_PX, CARD_HEIGHT_PX), "white")

def parallel_download_images(url_list, max_workers=10):
    """
    使用 ThreadPoolExecutor 進行並行下載
    """
    images = [None] * len(url_list) # 預先建立空列表以保持順序
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(download_single_image, url): i for i, url in enumerate(url_list)}
        
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                images[idx] = future.result()
            except Exception as e:
                print(f"下載任務異常 (Index {idx}): {e}")
                images[idx] = Image.new("RGB", (CARD_WIDTH_PX, CARD_HEIGHT_PX), "white")
    return images

def generate_pdf_from_pil_images(pil_images, counts, game_type="WS"):
    """
    接收Image 列表，生成 PDF
    """
    final_card_images = []
    
    for i, img in enumerate(pil_images):
        if i >= len(counts): break
        count = counts[i]
        
        # WS 特殊邏輯：名場面轉向
        if game_type == "WS":
            if img.width > img.height:
                img = img.rotate(90, expand=True)
        
        img = img.resize((CARD_WIDTH_PX, CARD_HEIGHT_PX), Image.LANCZOS)
        
        for _ in range(count):
            final_card_images.append(img.copy())

    pdf_pages = []
    for i in range(0, len(final_card_images), CARDS_PER_PAGE):
        page = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), "white")
        batch = final_card_images[i : i + CARDS_PER_PAGE]
        for idx, card_img in enumerate(batch):
            row = idx // COLS
            col = idx % COLS
            x = col * CARD_WIDTH_PX
            y = row * CARD_HEIGHT_PX
            page.paste(card_img, (x, y))
        pdf_pages.append(page)

    pdf_buffer = io.BytesIO()
    if pdf_pages:
        pdf_pages[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pdf_pages[1:])
    else:
        Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), "white").save(pdf_buffer, format="PDF")
    
    pdf_buffer.seek(0)
    return pdf_buffer

# ===========================
# WS (Wei Schwarz) 主邏輯
# ===========================
def process_ws_logic(driver, url):
    driver.get(url)
    driver.fullscreen_window()
    delay_time = 10
    card_data = []
    
    # === 1. 爬取卡號列表 ===
    try:
        main = WebDriverWait(driver, delay_time).until(
            EC.presence_of_element_located((By.ID, "main"))
        )
        section_main = main.find_element(By.CLASS_NAME, "main-container")

        sections = WebDriverWait(section_main, delay_time).until(
            EC.presence_of_element_located((By.XPATH, '//section[contains(@class, "deck-content") and contains(@class, "mt-8")]'))
        )
        # 獲取所有卡片元素
        cards = WebDriverWait(sections, delay_time).until(  
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".select-none.relative.max-w-\\[15rem\\]"))
        )

        for card in cards:
            try:
                card_secret_fir = card.find_element(By.CSS_SELECTOR, '.relative.cursor-pointer.group')
                card_secret_sec = card_secret_fir.find_element(By.CSS_SELECTOR, ".w-full.bg-zinc-900.-mt-2.pb-2.pt-4.px-2.rounded-b-xl.flex.flex-col.gap-2")
                ans_secret = card_secret_sec.find_element(By.CSS_SELECTOR, ".flex.items-center.justify-between")
                secret = ans_secret.find_element(By.TAG_NAME, 'span')
                # 將獲得的文本添加到列表中
                card_data.append(secret.text)
            except Exception:
                
                card_data.append('')
    
    except Exception as e:
        # 意外排除
        print(f"WS 爬蟲錯誤 (解析失敗): {e}")
        return None, None

    # === 2. 計算數量邏輯 ===
    speace = []
    
    # 只要 card_data 不為空 就進行統計
    if card_data:
        current_count = 0
        
        # 遍歷原始抓到的資料 (包含空字串)
        for text in card_data:
            if text != '':
                # 如果讀到新卡片，且之前已經有在計數了，就把前一張的數量存起來
                if current_count > 0:
                    speace.append(current_count)
                
                # 重置計數器，這張卡本身算 1 張
                current_count = 1
            else:
                # 如果是空字串，代表是上一張卡片的重複，數量 +1
                current_count += 1
        if current_count > 0:
            speace.append(current_count)

    # 確保資料乾淨
    clean_card_data = [text for text in card_data if text.strip()]
    
    # 防呆檢查
    while len(speace) < len(clean_card_data):
        speace.append(1)

    print(f"WS: 成功解析，共 {len(clean_card_data)} 種卡片")
    
    # === 3. 取得圖片網址 ===
    img_urls = []
    driver.get("https://ws-tcg.com/cardlist/")
    
    # 處理 Cookie 視窗
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "CybotCookiebotDialogBodyButtonDecline"))).click()
    except: pass

    print(f"WS: 正在搜尋 {len(clean_card_data)} 張卡片網址...")
    
    for code in clean_card_data:
        try:
            input_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.card-search-table input[name="keyword"]')))
            input_box.clear()
            input_box.send_keys(code)
            
            # 點擊搜尋
            driver.find_element(By.CSS_SELECTOR, 'input[name="button"]').click()
            
            # 等待圖片結果
            img_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.search-result-table-container table th a img')))
            img_urls.append(img_element.get_attribute("src"))
        except Exception as e:
            print(f"WS 搜尋失敗: {code}")
            img_urls.append(None) # 佔位符，避免順序錯亂

    return img_urls, speace

# ===========================
#  OPCG (One Piece) 主邏輯區 
# ===========================
def process_opcg_logic(driver, raw_text):
    """
    解析格式: 1xOP13-003 ...
    """
    card_search_list = []
    counts = []
    
    # 1. 解析文字
    try:
        matches = re.findall(r'(\d+)x([A-Z0-9-]+)', raw_text, re.IGNORECASE)
        if not matches:
            print("OPCG 解析失敗: 格式不正確")
            return None, None
            
        for qty, code in matches:
            counts.append(int(qty))
            card_search_list.append(code.upper())
            
        print(f"OPCG 解析成功: {len(card_search_list)} 種卡片")
    except Exception as e:
        print(f"OPCG 解析錯誤: {e}")
        return None, None

    # 2. 搜尋圖片
    img_urls = []
    target_site_url = "https://asia-tw.onepiece-cardgame.com/cardlist/"
    
    try:
        driver.get(target_site_url)
        driver.maximize_window()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "footer")))
        
        
        try:
            print("正在設定篩選條件: ALL...")
            # 點擊「收錄」按鈕
            series_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-selmodalbtn='series']"))
            )
            driver.execute_script("arguments[0].click();", series_btn)
            time.sleep(0.5)
            # 點擊「ALL」
            all_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'seriesCol')]//li[contains(text(), 'ALL')] | //li[contains(text(), 'ALL')]"))
            )
            driver.execute_script("arguments[0].click();", all_btn)
            time.sleep(0.5)
            print("篩選條件已設定")
        except Exception as e:
            print(f"篩選條件設定略過 : {e}")
            
    except Exception as e:
        print(f"網站連線失敗: {e}")
        return None, None

    print(f"OPCG: 正在搜尋 {len(card_search_list)} 張卡片...")

    for code in card_search_list:
        try:
            # 1. 找到搜尋框
            input_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "form-free"))
            )
            input_box.clear()
            input_box.send_keys(code)
            
            # 2. 點擊搜尋按鈕
            form = driver.find_element(By.CLASS_NAME, "commonBtn.submitBtn")
            search_btn = form.find_element(By.CSS_SELECTOR, 'input[type="submit"][value="SEARCH"]')
            driver.execute_script("arguments[0].click();", search_btn)
            time.sleep(0.8)
            
            
            # 3. 等待結果區塊
            resultCol = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "resultCol"))
            )
            # 4. 抓取圖片
            # 只抓取 .resultCol 下面 .modalOpen 裡的 img
            found_images = WebDriverWait(resultCol, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@class, 'modalOpen')]//img"))
            )
            if found_images:
                # 選取最後一張
                if len(found_images) >= 3:
                    target_img = found_images[-2]
                else:
                    target_img = found_images[-1]
                src = target_img.get_attribute("src")
                
                print(f"找到圖片網址: {src}")
                
                WebDriverWait(driver, 100).until(
                lambda d: "dummy.gif" not in target_img.get_attribute("src")
                )

                img_urls.append(src)
                print(f"OPCG: {code} 抓取成功 (第 {len(found_images)} 張)")
            else:
                print(f"OPCG: {code} 找不到圖片")
                img_urls.append(None)
            
        except Exception as e:
            print(f"OPCG 搜尋失敗 {code}: {e}")
            img_urls.append(None)

    return img_urls, counts

# ===========================
#  UA (Union Arena) 主邏輯
# ===========================
def process_ua_logic(driver, url):
    # 1. 解析網址
    try:
        version_match = re.search(r"Version=([A-Z0-9]+)", url)
        version = version_match.group(1) if version_match else "未知"
        deck_str = url.split("Deck=")[-1]
        
        card_entries = deck_str.split("|")
        card_search_list = []
        counts = []
        is_blood_card = []
        
        for entry in card_entries:
            match = re.match(r"(\d)([A-Z]+)(\d*[A-Z]*)_(\d{4})(_\d)?", entry)
            if match:
                quantity = int(match.group(1))
                name = match.group(2) + match.group(3)
                number = match.group(4)
                suffix = match.group(5)
                
                version_index = 0
                if suffix == "_2": version_index = 1
                elif suffix == "_3": version_index = 2
                is_blood_card.append(version_index)

                full_code = f"{name}/{version}-{number[0]}-{number[1:]}"
                card_search_list.append(full_code)
                counts.append(quantity)
                
    except Exception as e:
        print(f"UA 解析錯誤: {e}")
        return None, None

    # 2. 收集圖片網址
    img_urls = []
    driver.get("https://www.unionarena-tcg.com/jp/cardlist/?search=true")
    
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "cardMainWrap")))
    except: pass

    print(f"UA: 正在搜尋 {len(card_search_list)} 張卡片網址...")

    for i, code in enumerate(card_search_list):
        try:
            input_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "freewords")))
            input_field.clear()
            input_field.send_keys(code)
            
            submit_btn = driver.find_element(By.CLASS_NAME, "submitBtn").find_element(By.TAG_NAME, "input")
            driver.execute_script("arguments[0].click();", submit_btn)

            time.sleep(0.5) 
            
            # 定位結果列表
            card_list_col = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".cardlistCol"))
            )
            li_elements = card_list_col.find_elements(By.TAG_NAME, "li")
            
            target_li = None
            target_ver = is_blood_card[i]

            if target_ver == 1 and len(li_elements) > 1:
                target_li = li_elements[1]
            elif target_ver == 2 and len(li_elements) > 2:
                target_li = li_elements[2]
            else:
                target_li = li_elements[0] # 預設第一張

            # 抓取圖片網址
            img_element = target_li.find_element(By.TAG_NAME, "img")
            
            # 等待 dummy.gif 消失
            WebDriverWait(driver, 5).until(
                lambda d: "dummy.gif" not in img_element.get_attribute("src")
            )
            
            img_urls.append(img_element.get_attribute("src"))
                    
        except Exception as e:
            print(f"UA 搜尋失敗 {code}: {e}")
            img_urls.append(None)

    return img_urls, counts

# ===========================
# 🚀 Flask 路由
# ===========================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream_logs/<session_id>')
def stream_logs(session_id):
    def event_stream():
        # 為這個 session 建立一個佇列
        if session_id not in log_queues:
            log_queues[session_id] = Queue()
        
        while True:
            # 從佇列取出訊息，如果沒有就阻塞等待
            message = log_queues[session_id].get()
            if message == "DONE":
                break
            # SSE 格式: data: <message>\n\n
            yield f"data: {message}\n\n"
    
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    url = data.get('url', '').strip()
    session_id = data.get('session_id') # 取得前端傳來的 ID
    need_zip = data.get('need_zip', False) 
    if not url: return jsonify({'error': '請提供網址'}), 400

    send_log(session_id, f"收到請求，開始分析...")
    print(f"收到請求: {url}")
    driver = get_driver()
    
    try:
        # === 智慧判斷邏輯更新 ===
        raw_input = url  
        lower_input = raw_input.lower()

        if "rugiacreation" in lower_input:
            send_log(session_id, "模式: Union Arena")
            img_urls, counts = process_ua_logic(driver, url) 
            game_type = "UA"
            
        elif "bottleneko" in lower_input or "decklog" in lower_input:
            send_log(session_id, "模式: Wei Schwarz")
            img_urls, counts = process_ws_logic(driver, url)
            game_type = "WS"
            
        elif "xop" in lower_input or "xst" in lower_input or "xeb" in lower_input:
            send_log(session_id, "模式: One Piece (OPCG)")
            img_urls, counts = process_opcg_logic(driver, url) 
            game_type = "OPCG"
            
        else:
            return jsonify({'error': '無法識別輸入格式，請確認是網址或正確的代碼清單'}), 400
        

        if not img_urls or not counts:
            return jsonify({'error': '解析失敗或找不到卡片'}), 400

        # === 2. 並行下載圖片 (Python Threading) ===
        send_log(session_id, f"解析完成，準備下載 {len(img_urls)} 張圖片...")
        
        # 下載部分
        pil_images = parallel_download_images(img_urls, max_workers=10)
        send_log(session_id, "圖片下載完畢，正在合成 PDF...")

        pdf_buffer = generate_pdf_from_pil_images(pil_images, counts, game_type)
        send_log(session_id, "PDF 合成完成！準備回傳...")

        if need_zip:
            send_log(session_id, "正在打包圖檔與 PDF (ZIP)...")
            
            # 建立記憶體中的 ZIP 檔
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                
                # 1. 寫入 PDF
                zf.writestr(f"{game_type}_Deck.pdf", pdf_buffer.getvalue())
                
                # 2. 寫入每一張圖片
                for i, img in enumerate(pil_images):
                    # 將 PIL Image 轉為 Bytes
                    img_byte_arr = io.BytesIO()
                    # 預設存為 JPG 以節省空間，若要透明度可改 PNG
                    img.save(img_byte_arr, format='JPEG', quality=90) 
                    
                    # 寫入 ZIP (放在 images 資料夾內)
                    # 檔名範例: images/01.jpg
                    zf.writestr(f"images/{i+1:02d}.jpg", img_byte_arr.getvalue())

            zip_buffer.seek(0)
            send_log(session_id, "打包完成！開始傳輸...")
            
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name=f'{game_type}_Deck_Bundle.zip', # 副檔名是 .zip
                mimetype='application/zip'
            )
        
        else:
            # 不需要 ZIP，就照舊回傳 PDF
            send_log(session_id, "PDF 合成完成！準備回傳...")
            return send_file(
                pdf_buffer,
                as_attachment=True,
                download_name=f'{game_type}_Deck.pdf',
                mimetype='application/pdf'
            )


    except Exception as e:
        print(f"嚴重錯誤: {e}")
        if driver.service.process: driver.quit() # 確保出錯時關閉
        return jsonify({'error': str(e)}), 500
    finally:
        if session_id in log_queues:
            log_queues[session_id].put("DONE") # 通知 SSE 結束
        
        driver.quit() 

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
