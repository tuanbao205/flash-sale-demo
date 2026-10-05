# Bản mới: có Swagger UI

Chạy `python server.py`, mở **http://localhost:8080/docs**. Swagger UI tải JS/CSS từ unpkg.com nên cần Internet; backend vẫn chỉ dùng thư viện chuẩn Python.

## Thử dễ hiểu bằng Swagger

Mỗi API: mở mục → **Try it out** → **Execute** → xem **Response body**.

1. **Login**: giữ user=bao, device=device-bao → Execute. Session tự điền vào Authorize.
2. **Join** → Execute. WAITING nghĩa là đang chờ admin chọn người mua.
3. Bấm **Authorize** ở đầu trang → nhập **adminAuth** bằng Admin key in trong terminal → Authorize → Close. Mục sessionAuth đã được tự điền từ login.
4. **Admin draw** → Execute. Hệ thống chọn tối đa số hàng còn lại; với một người đăng ký khi kho còn hàng, selected=1.
5. **Ticket** → Execute. SELECTED nghĩa là được mua. Vé tự lưu trong Swagger.
6. **Buy**: giữ ticket=AUTO_TICKET, header Idempotency-Key=buy-bao-001 → Execute. Nhận ORDER_CREATED và order_id.
7. **Stats** → Execute. Kết quả stock=99, orders=1, invariant_ok=true nếu ban đầu là demo mới.
8. Gọi **Buy** lại và gọi **Stats** lại: vẫn 99 sản phẩm, một đơn. Đây là chống double click/retry.

Để thử tài khoản khác, đăng ký họ **trước khi Admin draw**. Khi đổi user cần Login lại, lấy Ticket lại và đổi Idempotency-Key. Bốc suất chỉ chạy một lần. Muốn mở đợt mới: dừng server rồi chạy lại; kho vẫn giữ. Muốn reset về 100: dừng server và xóa sale.db, sale.db-wal, sale.db-shm nếu có (chỉ dữ liệu demo).

## Giải thích test tự động

Swagger kiểm tra API từng bước. `test.bat` kiểm tra nhiều người mua cùng lúc: giả lập 1.000 yêu cầu bằng 100 worker. Database phải cho đúng 100 đơn, 900 SOLD_OUT, kho 0. Không có nghĩa là 1.000 người được chọn trong hàng chờ thật: test cố ý vượt qua giới hạn admission để kiểm tra database là lớp bảo vệ cuối.

Lỗi INVALID_TICKET trong giao diện cũ thường do chưa Admin draw và chưa lấy Ticket, hoặc dùng vé không còn hợp lệ sau khi restart. Bản mới hiển thị hướng dẫn khi chưa có vé.

Tài liệu triển khai và giới hạn của demo ở bên dưới.

---

# Demo Flash Sale — 100 sản phẩm

Demo bài test tuyển dụng: tránh overselling, mua trùng; chống spam và bốc ngẫu nhiên suất mua. Python 3.10+; chỉ dùng thư viện chuẩn, không cần pip, Docker hay Redis. Giao diện tiếng Việt.

## 1. Chạy trên Windows

1. Kiểm tra `python --version` (nếu máy dùng `py`, thay `python` bằng `py`).
2. Chạy `python server.py` hoặc mở `run.bat`.
3. Mở http://localhost:8080. Giữ terminal đang chạy.
4. Đăng nhập demo → Vào hàng chờ. Đổi tên tài khoản và thiết bị để đăng ký thêm người.
5. Copy Admin key từ terminal vào ô quản trị → Đóng đăng ký & bốc ngẫu nhiên.
6. Đăng nhập lại tài khoản đã đăng ký → Kiểm tra kết quả → Mua ngay.
7. Bấm Mua ngay nhiều lần: nhận lại cùng mã đơn, kho chỉ giảm một lần.

Khóa admin sinh ngẫu nhiên mỗi lần chạy; không phải mật khẩu tài khoản thật. Server chỉ lắng nghe localhost.

## 2. Kiểm thử tự động

Chạy `python -m unittest discover -s tests -v` hoặc mở `test.bat`.

- 1.000 yêu cầu mua, tối đa 100 worker chạy đồng thời: 100 đơn, 900 SOLD_OUT, tồn kho 0.
- 1.000 người đăng ký: chọn đúng 100 tài khoản; đăng ký trùng không tăng xác suất.
- 100 yêu cầu mua lặp từ cùng một người: chỉ một mã đơn, kho giảm một.
- Tài khoản thứ ba trên cùng thiết bị bị từ chối; vượt ngưỡng bị 429.
- Token giả, sửa chữ ký, dùng token người khác bị từ chối.
- Cố ý làm INSERT thất bại: trừ kho được rollback, kho vẫn 100.
- Khởi tạo lại service giữ đơn và kho; idempotency key trùng giữa hai người bị từ chối.
- Restart với kho còn 99: bốc đúng tối đa 99 suất; identity/ticket sai kiểu dữ liệu bị từ chối.

Test 1.000 yêu cầu **cố ý cho lớp admission cấp quá 100 vé**, để chứng minh database vẫn ngăn overselling độc lập với hàng chờ. Đây là bài test service có database thật, không phải 1.000 HTTP request cùng một thời điểm; không phải benchmark 100.000 người. `TEST_RESULTS.txt` là kết quả thực thi đính kèm.

### Demo HTTP riêng

Dùng database mới: dừng server, xóa `sale.db`, `sale.db-wal`, `sale.db-shm` nếu có (chỉ dữ liệu demo), rồi chạy lại server. Trong terminal thứ hai:

```powershell
python tests/http_demo.py --admin-key "KEY_IN_TRONG_TERMINAL"
```

Script đăng ký 100 tài khoản qua HTTP, bốc suất, gửi 100 yêu cầu mua bằng 30 worker, kiểm tra mua lại và token giả. Mỗi lần chạy cần demo mới. Không chạy trên sự kiện đã đóng đăng ký.

## 3. Luồng xử lý và code quan trọng

1. `/api/demo/login`: cấp session demo; user/device là dữ liệu giả lập.
2. `/api/join`: xác minh session, rate limit theo IP, giới hạn hai tài khoản trên thiết bị, chống đăng ký trùng.
3. `/api/admin/draw`: admin đóng đăng ký; dùng bộ sinh ngẫu nhiên hệ thống xáo danh sách, chọn tối đa số hàng còn lại trong kho.
4. `/api/ticket`: trả token HMAC do server ký, chứa user/event/expiry; chỉ người được chọn có vé mua, TTL 10 phút.
5. `/api/buy`: kiểm tra session + chữ ký + người sở hữu + expiry + quyền được chọn; kiểm tra Idempotency-Key; giới hạn user/device/IP; giới hạn số transaction đồng thời.
6. Database thực hiện `BEGIN IMMEDIATE`; kiểm tra đơn tồn tại và key trùng; trừ kho có điều kiện; tạo đơn; COMMIT. Lỗi thì ROLLBACK toàn bộ.

```sql
UPDATE stock SET remaining = remaining - 1
WHERE id = 1 AND remaining > 0;
```

Chỉ tạo đơn nếu affected rows = 1. `CHECK(remaining >= 0)`, `UNIQUE(user_id)`, `UNIQUE(request_key)` và transaction là các lớp bảo vệ. Không dùng đọc kho rồi ghi lại ở hai thao tác rời. Trong demo này một sự kiện, một sản phẩm, số lượng luôn 1. Client không thể gửi quantity để tăng số lượng.

Bất biến: `stock + count(orders) = 100`, stock >= 0, mỗi user tối đa một đơn. Mua lại trả mã đơn cũ kể cả key mới (quy tắc một người một đơn); key dùng bởi người khác trả conflict. Kết quả ORDER_CREATED nghĩa là đơn đã COMMIT, chưa phải đã thanh toán.

## 4. API

| Endpoint             | Header / body                                          | Vai trò                      |
| -------------------- | ------------------------------------------------------ | ----------------------------- |
| POST /api/demo/login | `{ "user": "bao", "device": "pc-bao" }`              | Session demo                  |
| POST /api/join       | Authorization: Bearer session                          | Đăng ký hàng chờ         |
| POST /api/admin/draw | X-Admin-Key                                            | Đóng hàng chờ, bốc suất |
| POST /api/ticket     | Authorization                                          | Lấy kết quả/token          |
| POST /api/buy        | Authorization, Idempotency-Key;`{ "ticket": "..." }` | Tạo đơn                    |
| GET /api/stats       | Không                                                 | Kho, đơn, metric demo       |

## 5. Chống bot và công bằng: điều gì đã làm, điều gì chưa

Đã có: rate limit IP/user/device, giới hạn tài khoản theo thiết bị, token server ký, chống dùng token người khác, một người một đơn, random draw trong nhóm đăng ký đã đóng. Tốc độ click trong cửa sổ đăng ký không quyết định thắng.

**Không chứng minh phân biệt được người thật và bot.** Login cho tự khai danh tính; device do client khai và có thể giả mạo. Bot tạo nhiều danh tính/thiết bị vẫn tăng cơ hội. Ngưỡng dùng để dễ demo, không phải số tối ưu. Không dùng CAPTCHA thật, fingerprint thật, xác minh số điện thoại hay WAF. Random draw không giải quyết được nhiều tài khoản giả. Không dựa vào tên API bí mật hay client giữ secret để chống bot.

Bản thật cần tài khoản đã xác minh, CAPTCHA được server kiểm chứng theo rủi ro, WAF, giới hạn đa chiều có lưu trữ dùng chung và cơ chế xử lý người dùng chung IP. Device fingerprint chỉ là tín hiệu. Với fairness, công bố cửa sổ đăng ký, tiêu chí hợp lệ và quy tắc bốc suất; lưu audit draw. Demo chưa có audit và chưa chuyển suất của người trúng bỏ mua.

## 6. Mở rộng lên 100.000 người

SQLite + HTTP server chuẩn phục vụ minh họa cục bộ, không dùng triển khai tải này. Database là nguồn dữ liệu chuẩn. PostgreSQL transaction vẫn cần conditional update + unique constraint, không chỉ dựa vào Redis.

Kiến trúc dự kiến: CDN/WAF → waiting room → admission/rate limit dùng Redis → API → PostgreSQL. Chỉ người có admission hợp lệ mới đến thao tác ghi. Với 100 đơn, có thể ghi trực tiếp bằng pool giới hạn; không bắt buộc thêm Kafka chỉ vì có 100 người thắng.

Nếu dùng Redis reserve + message queue, phải giải quyết khoảng trống giữa trừ Redis và publish message. Có thể dùng Redis Lua ghi reservation và XADD vào Redis Stream trong cùng script (các key cùng hash slot khi dùng Cluster); worker dùng transaction DB và unique reservation ID; chỉ ACK sau COMMIT, retry không tạo thêm đơn. Redis failover vẫn có thể mất reservation nên DB là chốt cuối. Không trả “mua thành công” chỉ vì reserve được trong Redis. Cần theo dõi trạng thái, đối soát, retry/thu hồi reservation đúng một lần.

Thanh toán thực tế cần trạng thái PENDING_PAYMENT/PAID/EXPIRED, thời hạn giữ suất, webhook idempotent, trả kho đúng một lần và xử lý payment đến muộn. Demo chỉ tạo đơn, chưa tích hợp payment hay trả kho.

## 7. Giới hạn vận hành

Orders và stock lưu bền trong SQLite. Session, hàng chờ, selection, rate limit nằm trong RAM một process, mất khi restart; các token cũ hết hiệu lực vì secret đổi. Khởi động lại không reset kho. Nhiều instance cần lưu trạng thái dùng chung. Demo không có cleanup hàng chờ/session, chính sách dữ liệu hoặc bảo vệ trước traffic lớn. Stats đọc tồn kho và số đơn trong cùng một snapshot SQLite; trạng thái hàng chờ vẫn chỉ thuộc process hiện tại. Không để demo này ra Internet.

## 8. Giải thích khi trình bày

“Em dùng cập nhật tồn kho có điều kiện và tạo đơn trong cùng transaction, kèm constraint và idempotency để không bán vượt kho hay tạo đơn trùng. Demo 1.000 yêu cầu với 100 worker cho đúng 100 đơn. Để giảm lợi thế bot click nhanh, em cho đăng ký vào hàng chờ rồi bốc ngẫu nhiên tối đa 100 người. Rate limit và token ký là lớp bổ sung; bản thật cần xác minh danh tính và chống bot tại server.”
