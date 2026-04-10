# CARD PRINTER PRO 
<img width="2868" height="1708" alt="螢幕擷取畫面 2026-04-10 171351" src="https://github.com/user-attachments/assets/22b1d06e-0b11-4c48-bcb5-a0c1856029cb" />

CARD PRINTER PRO 是一個專為實體卡牌玩家開發的自動排版與印製輔助工具。

此專案可根據使用者的需求，選擇對應的卡牌遊戲，透過自動化腳本抓取組牌網的資料，並一鍵產出完美符合 A4 尺寸、可直接列印的 PDF 檔案 。

## ✨ 核心功能

* **跨遊戲支援**：目前支援 Union Arena (UA)、Weiß Schwarz (WS) 與 One Piece Card Game (OPCG) 三大卡牌遊戲 。
* **Selenium 自動化**：透過 Selenium 模擬瀏覽器自動抓取卡牌圖片與資訊 。
* **一鍵生成 PDF**：貼上對應的代碼後，即可自動排版並產出 PDF 檔案。
* **圖片打包下載**：支援勾選「同時下載圖片檔」，在輸出結束後會將原始卡牌圖檔與 PDF 一併打包成 ZIP 壓縮檔匯出。

## 📸 畫面預覽

### 操作介面
<img width="2868" height="1708" alt="螢幕擷取畫面 2026-04-10 171351" src="https://github.com/user-attachments/assets/f4b6d69d-124e-444b-9dfb-e2e8c4e06a98" />


### 執行與輸出結果
<img width="1637" height="998" alt="螢幕擷取畫面 2026-04-10 172422" src="https://github.com/user-attachments/assets/dcfde556-f754-4d07-b5a4-dedada6d68ea" />
<img width="1637" height="998" alt="螢幕擷取畫面 2026-04-10 172422" src="https://github.com/user-attachments/assets/5920f1ec-2871-4775-93f1-9f11db70cd2b" />

<img width="2449" height="1919" alt="螢幕擷取畫面 2026-04-10 172736" src="https://github.com/user-attachments/assets/08fe00d0-e3c3-4f9b-8bf1-0d80c059f254" />

*ZIP 壓縮檔內容預覽（包含 PDF 與獨立圖檔）* 
<img width="1182" height="385" alt="螢幕擷取畫面 2026-04-10 173431" src="https://github.com/user-attachments/assets/18ab7eff-abd2-42d1-95fe-4cbc87af92fc" />
<img width="2543" height="550" alt="螢幕擷取畫面 2026-04-10 173532" src="https://github.com/user-attachments/assets/269fd20b-3485-402d-a364-1817de8ea206" />



## 📖 使用說明

### 各遊戲代碼取得流程 

1.  **Union Arena (UA)**
    * 前往 `Rugia Creation` 組牌網。
    * 點擊左側的「複製牌組 (Deck URL)」，直接貼到本工具的輸入框中 。
2.  **Weiß Schwarz (WS)**
    * 前往 `貓罐子 (BottleNeko)` 組牌網。
    * 組完牌後複製「牌組網址 (Deck Log)」，貼到輸入框中 。
3.  **One Piece Card Game (OPCG)** 
    * 前往 `OP Meta Builder` 組牌網 。
    * 在左側牌組預覽區找到「Export Deck List」，點擊複製文字內容 ，貼到輸入框中。

## [cite_start]✂️ 手作流程教學

拿到程式生成的 PDF 後，請依照以下步驟製作實體卡牌：

1.  [cite_start]**前往影印店**：帶著 PDF 檔案前往影印店，建議選擇「彩色列印」，並使用 A4 規格列印 。
2.  [cite_start]**設定列印參數**：在列印設定介面中，**務必確認將列印比例設定為「實際大小」或「100%」** ，避免卡牌尺寸跑版。
3.  [cite_start]**裁切與裝套**：沿著邊緣裁下卡片，放入卡套中，並在後方塞入一張廢卡增加厚度，即可完成！ 
