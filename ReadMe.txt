=========================
🤖 ChatGPT Discord Bot
=========================

📄 GIỚI THIỆU:
Đây là chatbot Discord viết bằng Python, sử dụng OpenRouter API để tạo phản hồi AI.
Bot chỉ hoạt động trong kênh đã được thiết lập bằng lệnh `-ai setup`.

✅ Tính năng:
- Bộ nhớ theo từng người dùng
- Hiển thị đang nhập (typing indicator)
- Thiết lập khóa/mở khóa kênh
- Lệnh tiền tố đơn giản

=========================
📁 TỆP DỰ ÁN:
=========================

1. bot.py           → Tập lệnh Python chính chạy bot.
2. config.json      → Tệp cấu hình (API key, model và cài đặt).
3. requirements.txt → Phụ thuộc Python cho Katabump hoặc chạy cục bộ.

=========================
⚙️ HƯỚNG DẪN CÀI ĐẶT:
=========================

🔸 BƯỚC 1: Chỉnh `config.json`

# Mở tệp `config.json` và cập nhật các mục sau:
- `"api_key"`: Thay bằng OpenRouter API key của bạn (dòng 2)
- `"system_context"`: Tùy biến tính cách trợ lý (dòng 4)
- `"error_message"`: Thông điệp dự phòng khi có lỗi (dòng 5)

🔸 BƯỚC 2: Chỉnh `bot.py`
- Ở cuối tệp, thay `<YOUR_BOT_TOKEN>` bằng Bot Token của bạn.

🔻 TRẠNG THÁI: (bot.py dòng 35-36)
- status=discord.Status.online # Tùy chọn: online, idle, dnd, invisible
- activity=discord...., name="<YOUR_STATUS_MESSAGE>"), # chúc vui vẻ!!!