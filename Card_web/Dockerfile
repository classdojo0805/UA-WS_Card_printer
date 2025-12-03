# 使用官方 Python 基礎映像檔
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 (包含 Chromium 瀏覽器與相依套件)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    chromium \
    chromium-driver \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# 設定環境變數，讓程式知道 Chromium 在哪
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# 複製 requirements.txt 並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼到容器內
COPY . .

# 暴露 Render 預設的 Port
EXPOSE 10000

# 啟動指令 (使用 gunicorn 作為生產環境伺服器)
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:10000", "--timeout", "120", "app:app"]