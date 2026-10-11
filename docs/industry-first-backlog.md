# Backlog — nhận định ngành

Ba câu về công bố, chỗ lệch hạng và bảng ngành dùng mô hình để đọc chữ. Chúng chưa được đo, và chưa được phép đổi `Được vào`.

Cổng số vẫn là cổng được phép chặn lệnh. Một câu chỉ được tham gia sau khi thắng phép so trên giai đoạn chọn và còn đúng trên giai đoạn xác nhận, cùng cách với nhận định tháng.

## Công bố trong ngành đang mở

Đưa các bài đã phát hành đến hết ngày nhận định, chỉ của các mã trong ngành cổng số đang mở. Hỏi công bố nào làm gãy luận điểm mà cờ bảng cân đối chưa bắt: kiểm toán chậm, doanh thu một lần, giao dịch với bên liên quan, hướng dẫn bị cắt. Mã bị nêu được ghi lại. Sau ba tháng, so lợi suất của nhóm bị nêu với nhóm không bị nêu. Nhóm bị nêu kém hơn trên cả hai giai đoạn thì câu này mới được phép loại mã khỏi danh sách khoanh.

## Chỗ cổng số và danh sách khoanh lệch nhau

Khi ngành mở mà hạng vị thế để một mã tăng mạnh ở ngoài danh sách, như `SHS`, hỏi một đoạn: với các công bố đã có của mã bị loại, có việc gì làm hạng vốn hóa và doanh thu chưa phản ánh đúng vị thế hay không. Câu trả lời lưu cùng tháng. Nó chỉ được đổi cách khoanh khi các tháng như vậy lặp lại trên cả hai giai đoạn.

## Định nghĩa cổng ngành

Báo cáo 2021-01-04–2026-10-09 cho precision ngành thấp hơn tỷ lệ nền ở cả hai giai đoạn (11,8% so 14,3%, và 11,0% so 12,5%): ngành đang mạnh hơn VN-Index 60 phiên tăng tiếp ít hơn một ngành bất kỳ. Hai câu hỏi cho lần đo sau, phải chốt trước khi chạy lại trên giai đoạn chọn:

- Có nên đổi định nghĩa "ngành mở", ví dụ độ rộng (tỷ lệ mã trong ngành vượt MA50) hoặc đà lợi nhuận quý, thay cho lợi suất 60 phiên?
- Ngưỡng precision gấp đôi tỷ lệ nền có phải mức đúng, khi tỷ lệ nền đã khoảng 12–14%?

Đổi định nghĩa là một quy tắc mới: đo lại từ đầu trên 2021–2024, không xem 2025–2026 trước khi chốt.

## Chuỗi `USDVND_MACRO`

Lịch sử Yahoo `USDVND=X` từ 2014 nằm ở `USDVND_MACRO`, tách khỏi `USDVND` mà cổng tiền tệ đọc từ TradingView. Hiện chưa có chỗ nào đọc chuỗi này: nó để dành cho lúc đo lớp vĩ mô liên thị trường trong backtest. Đừng ghi ngược lại vào `USDVND`.

## Rà bảng ngành một lần

Hỏi mã nào trong rổ đang bị gắn nhầm nghề, dựa trên mô tả kinh doanh đã công bố. Việc này sửa bảng ngành trước lần đo sau. Nó không phải tín hiệu hàng tháng, và không được thêm một nước hay một độ trễ mới sau khi đã thấy các đợt tăng.
