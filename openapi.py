"""OpenAPI 3.0 document served at /openapi.json."""
def schema(properties, required):
    return {'type':'object','required':required,'properties':{k:{'type':'string','example':v} for k,v in properties.items()}}
RESPONSES={
 '200':{'description':'Thành công; xem Response body bên dưới','content':{'application/json':{'schema':{'type':'object','additionalProperties':True}}}},
 **{str(code):{'description':text,'content':{'application/json':{'schema':{'type':'object','properties':{'error':{'type':'string'}}}}}} for code,text in [(400,'Request không hợp lệ'),(401,'Chưa đăng nhập'),(403,'Token sai hoặc thiếu quyền'),(409,'Hết hàng / sự kiện đã đóng / key trùng'),(429,'Gửi quá nhiều request'),(503,'Hệ thống bận; thử lại cùng key')]}}
def operation(summary, description, tag, body=None, security=None, parameters=None):
    op={'summary':summary,'description':description,'tags':[tag],'responses':RESPONSES}
    if body:op['requestBody']={'required':True,'content':{'application/json':{'schema':body}}}
    if security:op['security']=security
    if parameters:op['parameters']=parameters
    return op
AUTH=[{'sessionAuth':[]}]
SPEC={
 'openapi':'3.0.3',
 'info':{'title':'Flash Sale Demo — thử API từng bước','version':'2.0.0','description':'''Kho ban đầu 100 sản phẩm. Mở từng API → Try it out → Execute theo thứ tự 1 đến 6.
Login thành công sẽ tự điền session vào Authorize. Khi lấy được vé, UI tự điền ticket vào request mua nếu bạn để giá trị mẫu AUTO_TICKET.
Admin key lấy trong terminal chạy server; nhập qua Authorize → adminAuth. Đây là tài khoản/thiết bị giả lập, chưa xác minh người thật.
Swagger thử từng request; chạy test.bat để kiểm tra tải đồng thời. Đơn hàng và kho giữ lại sau restart; session/hàng chờ mất khi restart.'''},
 'servers':[{'url':'/','description':'Server đang chạy'}],
 'tags':[{'name':'1. Đăng nhập'},{'name':'2. Đăng ký'},{'name':'3. Quản trị'},{'name':'4. Vé mua'},{'name':'5. Mua hàng'},{'name':'6. Kiểm tra kho'}],
 'components':{'securitySchemes':{
 'sessionAuth':{'type':'http','scheme':'bearer','description':'Session từ login (không phải JWT). UI tự điền sau khi login. Chỉ dán session, không thêm Bearer.'},
 'adminAuth':{'type':'apiKey','in':'header','name':'X-Admin-Key','description':'Admin key in trong terminal khi chạy server.'}}},
 'paths':{
 '/api/demo/login':{'post':operation('1. Đăng nhập demo','Nhập user và device. UI tự lưu session của lần login gần nhất. Đổi user/device để giả lập người khác.','1. Đăng nhập',schema({'user':'bao','device':'device-bao'},['user','device']))},
 '/api/join':{'post':operation('2. Vào hàng chờ','Kết quả WAITING: đã đăng ký, chưa được mua. Một user chỉ có một lượt đăng ký.','2. Đăng ký',security=AUTH)},
 '/api/admin/draw':{'post':operation('3. Đóng hàng chờ và bốc suất','Nhập adminAuth trong Authorize. Bốc ngẫu nhiên tối đa 100 tài khoản từ danh sách đã đăng ký. Chỉ chạy một lần mỗi lần khởi động server.','3. Quản trị',security=[{'adminAuth':[]}])},
 '/api/ticket':{'post':operation('4. Lấy vé mua','SELECTED: được mua, trả ticket. WAITING: admin chưa bốc. NOT_SELECTED: không được chọn. UI tự lưu ticket sau kết quả SELECTED.','4. Vé mua',security=AUTH)},
 '/api/buy':{'post':operation('5. Mua một sản phẩm','Để ticket=AUTO_TICKET để UI dùng vé vừa lấy, hoặc dán ticket thật. Thành công: ORDER_CREATED. Bấm Execute lại: cùng order_id, replayed=true; tồn kho không giảm thêm.','5. Mua hàng',schema({'ticket':'AUTO_TICKET'},['ticket']),AUTH,[{'name':'Idempotency-Key','in':'header','required':True,'schema':{'type':'string','default':'buy-bao-001'},'description':'Dùng lại cùng key khi retry. Khi đổi người dùng, đổi key, ví dụ buy-ngoc-001.'}])},
 '/api/stats':{'get':operation('6. Xem tồn kho và số đơn','Nếu mới chỉ một người mua: stock=99, orders=1, invariant_ok=true. Bấm mua lại nhiều lần thì số liệu vẫn giữ nguyên.','6. Kiểm tra kho')}
 }}
