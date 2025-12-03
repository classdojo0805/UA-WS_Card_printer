import os
import io
import re
import time
import requests
from math import floor
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, send_file, jsonify

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image

app = Flask(__name__)

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
    # 雲端環境必須的參數
    options.add_argument('--headless') # 絕對要無頭模式
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument("--window-size=1920,1080")
    
    # 檢測是否在 Docker/Render 環境 (透過環境變數)
    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin:
        # 如果是雲端環境，指定 Chrome 位置
        options.binary_location = chrome_bin
        # 在 Docker 裡，通常 chromedriver 已經在 PATH 中，或指定路徑
        service = Service(executable_path=os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver'))
    else:
        # 如果是本機電腦，自動安裝
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    return driver

# --- 核心工具：多執行緒下載器 ---
def download_single_image(url):
    """
    下載單張圖片並回傳 PIL Image 物件 (記憶體運作，不存檔)
    """
    if not url or "dummy.gif" in url:
        # 回傳一張全白圖片作為佔位符
        return Image.new("RGB", (CARD_WIDTH_PX, CARD_HEIGHT_PX), "white")
        
    try:
        # 設定 timeout 避免卡死
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
        # 建立 future 到 index 的映射，確保順序正確
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
    接收 PIL Image 列表，生成 PDF
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
# 🔵 WS (Wei Schwarz) 邏輯 - 修正版
# ===========================
def process_ws_logic(driver, url):
    driver.get(url)
    delay_time = 10
    card_data = []
    
    # === 1. 爬取卡號列表 (改回你原本的寫法，確保抓得到) ===
    try:
        # 等待主元素加載
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
                # 使用你原本的層層剝開寫法，雖然長但最保險
                card_secret_fir = card.find_element(By.CSS_SELECTOR, '.relative.cursor-pointer.group')
                card_secret_sec = card_secret_fir.find_element(By.CSS_SELECTOR, ".w-full.bg-zinc-900.-mt-2.pb-2.pt-4.px-2.rounded-b-xl.flex.flex-col.gap-2")
                ans_secret = card_secret_sec.find_element(By.CSS_SELECTOR, ".flex.items-center.justify-between")
                secret = ans_secret.find_element(By.TAG_NAME, 'span')
                # 將獲得的文本添加到列表中
                card_data.append(secret.text)
            except Exception:
                # 遇到空格或結構不同時填入空字串
                card_data.append('')
    
    except Exception as e:
        print(f"WS 爬蟲錯誤 (解析失敗): {e}")
        return None, None

    # === 2. 計算數量邏輯 (你原本的邏輯) ===
    speace = []
    n = 0
    # 複製一份並多加一個空位防止溢出
    usingCardData = card_data.copy()
    usingCardData.append('')

    for i in range(0, len(usingCardData)):
        if usingCardData[i] != '' and i < len(usingCardData):
            for j in range(1, 5):
                if i+j < len(usingCardData) and usingCardData[i+j] == '':
                    n += 1
                elif i+j < len(usingCardData) and usingCardData[i+j] != '' and i+j > 0:
                    speace.append(n+1)
                    n = 0
                    break
            
            # 處理邊界情況
            if i == len(usingCardData)-1:
                # 這裡原本的邏輯有點複雜，為求穩妥，若最後還沒判定到，給預設值
                pass
    
    # 確保資料乾淨
    clean_card_data = [text for text in card_data if text.strip()]
    
    # 簡單補齊數量列表，防止長度不一致報錯
    while len(speace) < len(clean_card_data):
        speace.append(1)

    print(f"WS: 成功解析，共 {len(clean_card_data)} 種卡片")

    # === 3. 取得圖片網址 (這裡保持優化，只抓網址不下載) ===
    img_urls = []
    driver.get("https://ws-tcg.com/cardlist/")
    
    # 處理 Cookie 視窗
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "CybotCookiebotDialogBodyButtonDecline"))).click()
    except: pass

    print(f"WS: 正在搜尋 {len(clean_card_data)} 張卡片網址...")
    
    for code in clean_card_data:
        try:
            # 重新定位搜尋框
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
# 🟣 UA (Union Arena) 邏輯
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

            # 等待刷新，使用顯性等待取代 time.sleep (如果可能)
            # 這裡還是保留短暫 sleep 緩衝 AJAX，但主要是靠 Wait
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

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    url = data.get('url', '').strip()
    
    if not url: return jsonify({'error': '請提供網址'}), 400

    print(f"收到請求: {url}")
    driver = get_driver()
    
    try:
        # === 1. 取得網址列表 (Selenium 負責) ===
        if "rugiacreation.com" in url.lower():
            print(">>> 模式: Union Arena")
            img_urls, counts = process_ua_logic(driver, url)
            game_type = "UA"
        else:
            print(">>> 模式: Wei Schwarz")
            img_urls, counts = process_ws_logic(driver, url)
            game_type = "WS"
        
        driver.quit() # 任務完成，關閉瀏覽器，釋放資源

        if not img_urls or not counts:
            return jsonify({'error': '解析失敗或找不到卡片'}), 400

        # === 2. 並行下載圖片 (Python Threading 負責) ===
        print(f">>> 開始並行下載 {len(img_urls)} 張圖片...")
        pil_images = parallel_download_images(img_urls, max_workers=10)

        # === 3. 生成 PDF (Pillow 負責) ===
        print(">>> 正在生成 PDF...")
        pdf_buffer = generate_pdf_from_pil_images(pil_images, counts, game_type)

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

if __name__ == '__main__':
    # 讓 Render 動態決定 Port，本地則用 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)