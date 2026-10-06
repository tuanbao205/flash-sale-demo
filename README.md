# Flash Sale Demo — chống bán vượt kho

## Mục tiêu

Đây là demo cục bộ cho bài toán flash sale có **100 sản phẩm**. Mục tiêu là minh họa cách xử lý nhiều yêu cầu mua đồng thời mà vẫn:

- Không bán vượt số lượng tồn kho.
- Không tạo nhiều đơn cho cùng một tài khoản khi người dùng bấm mua hoặc retry.
- Cho người dùng đăng ký trước, sau đó bốc ngẫu nhiên người được quyền mua thay vì ưu tiên người click nhanh.
- Kiểm tra kết quả bằng Swagger UI và bộ test chạy đồng thời.

> Đây là ứng dụng demo để trình bày luồng xử lý và các lớp bảo vệ ở backend, không phải hệ thống bán hàng production. Tài khoản/thiết bị là dữ liệu giả lập; chưa có đăng nhập thật, thanh toán, CAPTCHA hay chống bot hoàn chỉnh.

## Chạy demo trên Windows

Yêu cầu Python **3.9 trở lên**. Project chỉ dùng thư viện chuẩn Python, không cần cài package bằng pip.

1. Mở terminal tại thư mục project.
2. Chạy `run.bat` hoặc:

   ```powershell
   python server.py
   ```

3. Giữ cửa sổ terminal đang chạy. Mở:
   - **http://localhost:8080** — giao diện demo.
   - **http://localhost:8080/docs** — Swagger UI.
4. Lấy **Admin key** được in trong terminal khi server khởi động.

Server chỉ lắng nghe trên `127.0.0.1`, phù hợp để demo trên máy cá nhân.

## Kịch bản trình bày đề xuất

Nên dùng giao diện tại **http://localhost:8080** để trình bày luồng chính. Swagger UI phù hợp khi muốn xem request, response và mã lỗi chi tiết.

1. **Đăng ký nhiều người trước khi bốc suất.** Nhập một user/device, bấm **Đăng nhập demo** rồi **Vào hàng chờ**. Đổi user (và device nếu muốn) để tạo thêm người tham gia.
2. **Đóng đăng ký và bốc suất.** Nhập Admin key lấy từ terminal, bấm **Đóng đăng ký & bốc ngẫu nhiên**. Với 100 sản phẩm, hệ thống chọn tối đa 100 người trong danh sách đã đăng ký. Bước này chỉ chạy một lần cho mỗi lần khởi động server.
3. **Kiểm tra một tài khoản.** Đăng nhập lại bằng user đã đăng ký, bấm **Kiểm tra kết quả**. Người được chọn nhận vé mua; người không được chọn không thể tạo đơn.
4. **Mua hàng.** Người có vé bấm **Mua ngay**. Response thành công có `ORDER_CREATED` và `order_id`.
5. **Chứng minh chống mua trùng.** Bấm **Mua ngay** lại với cùng tài khoản. Hệ thống trả về đơn đã tạo thay vì tạo đơn mới hoặc trừ kho thêm lần nữa.
6. **Kiểm tra số liệu.** `stock` là tồn kho, `orders` là số đơn và `invariant_ok` cho biết bất biến kho có còn đúng không.

### Trình diễn bằng Swagger UI

Trong Swagger, thực hiện theo thứ tự **Login → Join → Admin draw → Ticket → Buy → Stats**:

1. Gọi **Login** với user/device mẫu. Session được Swagger tự lưu để gọi các API cần đăng nhập.
2. Gọi **Join** để đưa tài khoản vào hàng chờ. Muốn đăng ký nhiều tài khoản, lặp lại Login → Join cho từng tài khoản trước khi bốc suất.
3. Bấm **Authorize**, nhập Admin key vào `adminAuth`, rồi gọi **Admin draw** sau khi đã đăng ký đủ người muốn tham gia.
4. Gọi **Ticket** để xem tài khoản có được chọn không.
5. Nếu được chọn, giữ `ticket=AUTO_TICKET` và gọi **Buy**. Swagger tự dùng vé vừa nhận. Khi thử nhiều tài khoản, đặt `Idempotency-Key` khác nhau cho từng tài khoản; giữ nguyên key khi retry cùng một yêu cầu.
6. Gọi lại **Buy** để xem kết quả retry và gọi **Stats** để kiểm tra kho.

Không cần nhập session vào `sessionAuth` thủ công sau khi Login thành công. Swagger UI tải thư viện giao diện từ unpkg.com nên cần Internet; backend demo vẫn chạy trên máy cục bộ.

## Cách xử lý giao dịch

Khi mua, backend kiểm tra session, vé do server ký, quyền sở hữu vé, thời hạn, idempotency key và giới hạn tần suất. Sau đó SQLite thực hiện transaction:

1. Bắt đầu transaction ghi.
2. Kiểm tra tài khoản hoặc idempotency key đã có đơn chưa.
3. Trừ kho có điều kiện — chỉ trừ khi còn sản phẩm.
4. Tạo đơn và commit. Nếu bước ghi lỗi, rollback cả transaction.

```sql
UPDATE stock SET remaining = remaining - 1
WHERE id = 1 AND remaining > 0;
```

Các constraint trong database và transaction là lớp bảo vệ cuối nếu nhiều yêu cầu chạy cùng lúc. Bất biến cần giữ là:

```text
stock + orders = 100
```

Một tài khoản chỉ có tối đa một đơn. Gửi lại yêu cầu mua sẽ nhận lại đơn cũ; `Idempotency-Key` được dùng để nhận diện retry và không được chia sẻ giữa các tài khoản khác nhau.

## API chính

| API | Mục đích |
| --- | --- |
| `POST /api/demo/login` | Tạo session demo từ user/device giả lập |
| `POST /api/join` | Đăng ký tham gia hàng chờ |
| `POST /api/admin/draw` | Đóng đăng ký và bốc ngẫu nhiên người được mua |
| `POST /api/ticket` | Kiểm tra kết quả và nhận vé mua nếu được chọn |
| `POST /api/buy` | Tạo đơn với vé mua và `Idempotency-Key` |
| `GET /api/stats` | Xem tồn kho, số đơn và trạng thái bất biến |

Swagger mô tả response thành công và các lỗi liên quan đến từng API, thay vì lặp toàn bộ mã lỗi cho mọi endpoint.

## Chạy kiểm thử

Chạy toàn bộ unit test:

```powershell
python -m unittest discover -s tests -v
```

Hoặc mở `test.bat`. Bộ test hiện kiểm tra các tình huống như:

- 1.000 yêu cầu mua đồng thời: database chỉ tạo đúng 100 đơn, 900 yêu cầu còn lại nhận `SOLD_OUT`, tồn kho về 0.
- Retry đồng thời từ cùng một người: chỉ có một đơn và kho chỉ giảm một lần.
- Đăng ký trùng, giới hạn tài khoản theo thiết bị, giới hạn tần suất và vé giả/vé của người khác.
- Rollback khi tạo đơn lỗi, xung đột idempotency key và bốc suất theo số hàng còn lại sau khi khởi động lại.
- Danh sách response được khai báo riêng theo endpoint trong OpenAPI.

**Lưu ý về test 1.000 yêu cầu:** test này cố ý cấp quyền mua cho 1.000 tài khoản để kiểm tra riêng database như lớp bảo vệ cuối. Đây không phải kết quả của một đợt bốc suất thật (với kho 100 thì chỉ tối đa 100 người được chọn), cũng không phải benchmark 100.000 người hay 1.000 HTTP request gửi qua mạng.

Để chạy thêm kịch bản HTTP riêng:

```powershell
python tests/http_demo.py --admin-key "ADMIN_KEY_IN_TRONG_TERMINAL"
```

Script này gửi các request qua HTTP và cần server đang chạy. Chạy trên trạng thái demo mới, trước khi hàng chờ đã được đóng.

## Phạm vi và giới hạn

- Tồn kho và đơn hàng được lưu trong `sale.db`; khởi động lại server **không** tự đặt lại kho.
- Session, hàng chờ, danh sách được chọn, rate limit và khóa ký session nằm trong bộ nhớ của một process. Chúng mất khi server dừng; session/vé cũ không còn hợp lệ sau khi khởi động lại.
- User và device do người demo tự nhập, không xác minh danh tính và có thể giả mạo. Giới hạn rate/device chỉ minh họa, không chứng minh có thể phân biệt người thật với bot.
- Bốc suất ngẫu nhiên giảm lợi thế của việc click nhanh trong nhóm đã đăng ký, nhưng chưa có CAPTCHA, xác minh tài khoản, audit kết quả bốc suất hay quy trình xử lý người trúng không mua.
- `ORDER_CREATED` chỉ có nghĩa là đơn đã được ghi thành công; demo chưa tích hợp thanh toán, giữ chỗ có thời hạn hay hoàn kho.
- Trạng thái RAM chỉ dùng chung trong một process. SQLite và HTTP server tích hợp phù hợp cho demo cục bộ, không phải cấu hình triển khai chịu tải lớn hoặc chạy nhiều instance.

Muốn bắt đầu lại với kho 100, hãy dừng server trước. Chỉ xóa các file dữ liệu demo `sale.db`, `sale.db-wal` và `sale.db-shm` (nếu có) khi bạn chắc chắn không cần giữ đơn hàng hiện tại, rồi khởi động server lại.

## Lời trình bày ngắn

> “Demo mô phỏng flash sale 100 sản phẩm. Người dùng đăng ký trước rồi hệ thống bốc ngẫu nhiên tối đa số suất còn hàng, tránh để tốc độ click quyết định kết quả. Khi mua, backend xác thực vé và thực hiện trừ kho có điều kiện cùng tạo đơn trong một transaction; constraint và idempotency giúp ngăn bán vượt kho và tạo đơn trùng. Bộ test chạy 1.000 yêu cầu mua đồng thời cho thấy database chỉ ghi tối đa 100 đơn. Đây là demo cục bộ, chưa xác minh danh tính, tích hợp thanh toán hay sẵn sàng cho production.”
