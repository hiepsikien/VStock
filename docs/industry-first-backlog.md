# Backlog — nhận định ngành

Ba câu về công bố, chỗ lệch hạng và bảng ngành dùng mô hình để đọc chữ. Chúng chưa được đo, và chưa được phép đổi `Được vào`.

Cổng số vẫn là cổng được phép chặn lệnh. Một câu chỉ được tham gia sau khi thắng phép so trên giai đoạn chọn và còn đúng trên giai đoạn xác nhận, cùng cách với nhận định tháng.

## Công bố trong ngành đang mở

Đưa các bài đã phát hành đến hết ngày nhận định, chỉ của các mã trong ngành cổng số đang mở. Hỏi công bố nào làm gãy luận điểm mà cờ bảng cân đối chưa bắt: kiểm toán chậm, doanh thu một lần, giao dịch với bên liên quan, hướng dẫn bị cắt. Mã bị nêu được ghi lại. Sau ba tháng, so lợi suất của nhóm bị nêu với nhóm không bị nêu. Nhóm bị nêu kém hơn trên cả hai giai đoạn thì câu này mới được phép loại mã khỏi danh sách khoanh.

## Chỗ cổng số và danh sách khoanh lệch nhau

Khi ngành mở mà hạng vị thế để một mã tăng mạnh ở ngoài danh sách, như `SHS`, hỏi một đoạn: với các công bố đã có của mã bị loại, có việc gì làm hạng vốn hóa và doanh thu chưa phản ánh đúng vị thế hay không. Câu trả lời lưu cùng tháng. Nó chỉ được đổi cách khoanh khi các tháng như vậy lặp lại trên cả hai giai đoạn.

## Định nghĩa cổng ngành

Lần đo này (2021-01-04–2026-10-09, chỉ số ngành dựng trên rổ 200 mã của năm) cho precision ngành 15,0% so tỷ lệ nền 13,0% ở giai đoạn chọn, và 6,0% so 9,8% ở giai đoạn xác nhận: trên giai đoạn chọn ngành đang mạnh hơn VN-Index 60 phiên tăng tiếp nhiều hơn một ngành bất kỳ, trên giai đoạn xác nhận thì ít hơn — hai giai đoạn không cùng dấu. Hai câu hỏi cho lần đo sau, phải chốt trước khi chạy lại trên giai đoạn chọn:

- Có nên đổi định nghĩa "ngành mở", ví dụ độ rộng (tỷ lệ mã trong ngành vượt MA50) hoặc đà lợi nhuận quý, thay cho lợi suất 60 phiên?
- Ngưỡng precision gấp đôi tỷ lệ nền có phải mức đúng, khi tỷ lệ nền đã khoảng 10–13%?

Đổi định nghĩa là một quy tắc mới: đo lại từ đầu trên 2021–2024, không xem 2025–2026 trước khi chốt.

### Rổ nào dựng chỉ số ngành của cổng sống

Báo cáo dựng chỉ số ngành trên rổ 200 mã của năm, và cờ mở chỉ sinh cho mã thuộc rổ giao dịch 100 mã — chốt ở lần đo này, trước đó cổng đo chỉ số ngành trên chính rổ giao dịch, nên phiên nào có ngành đủ ba mã trong rổ 200 mà không đủ trong rổ 100 thì cổng xét như cổ phiếu đơn lẻ, trong khi phép đo precision vẫn tính đó là phiên ngành mở.

Cổng sống thì không có rổ của năm: `pipeline`, `paper` và `backtest` đều dựng chỉ số ngành trên `DEFAULT_UNIVERSE` (106 mã cố định). Hai bên dùng cùng bộ nhãn ngành nhưng thành phần rổ khác nhau, nên khi bật cờ chặn, các phiên mà cổng sống mở sẽ không khớp từng phiên với các phiên đã đo. Phải chốt trước khi bật chặn: hoặc đo lại trên chính `DEFAULT_UNIVERSE`, hoặc cho cổng sống đọc rổ theo thời điểm như báo cáo.

Cùng lúc phát hành thêm cổ phiếu, chia tách hoặc thưởng cổ phiếu, vốn hóa bị lệch tạm thời: giá thật đã giảm từ ngày giao dịch không hưởng quyền, còn số cổ phiếu phải đủ 45 ngày mới cập nhật. Sai số này nhỏ hơn nhiều so với việc đo bằng giá đã điều chỉnh, nên chỉ ghi lại chứ chưa đổi luật.

### Độ mới của nến cuối khi chốt rổ

Cửa sổ thanh khoản lấy 20 phiên cuối của chính mã, nên mã bị tạm ngừng giao dịch dài vẫn xếp hạng bằng thanh khoản cũ: HPX nằm ở hạng 144/200 trong rổ 2024 dù phiên cuối là 2023-09-15, cách phiên chốt 109 ngày. Bắt nến cuối phải mới hơn một số ngày so với phiên chốt (ví dụ 10 ngày) là một tham số mới, đổi thành phần rổ của mọi năm, nên chưa đưa vào lần này; muốn dùng thì phải đo lại như một luật mới trước khi chốt.

## Chuỗi `USDVND_MACRO`

Lịch sử Yahoo `USDVND=X` từ 2014 nằm ở `USDVND_MACRO`, tách khỏi `USDVND` là chuỗi cổng tiền tệ đọc. Các dòng ngày thường Yahoo ghi vào `USDVND` trước lần tách vẫn ở lại làm số khởi đầu; từ đó TradingView ghi đè dần theo từng phiên. Hiện chưa có chỗ nào đọc chuỗi này: nó để dành cho lúc đo lớp vĩ mô liên thị trường trong backtest. Đừng ghi ngược lại vào `USDVND`.

## Rà bảng ngành một lần

Hỏi mã nào trong rổ đang bị gắn nhầm nghề, dựa trên mô tả kinh doanh đã công bố. Việc này sửa bảng ngành trước lần đo sau. Nó không phải tín hiệu hàng tháng, và không được thêm một nước hay một độ trễ mới sau khi đã thấy các đợt tăng.
