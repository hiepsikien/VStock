# Chốt trước — độ rộng làm bộ lọc tín hiệu phá nền

Chốt ngày 2026-10-12. Đây là giả thuyết 7.4.1 của `research/reports/breadth_gate_explained.md`.

**Mốc chốt** là tag `prereg/breadth-filter` trên GitHub. Ngày commit ở máy có thể đặt tùy ý, còn tag đã push thì kiểm chứng được. Tag trỏ tới commit chứa:

- file này;
- các hằng số `BREADTH_FILTER_*` trong `research/app/config.py`;
- lệnh đếm và lệnh đo `research/app/breadth_filter.py`, kèm test `research/tests/test_breadth_filter.py`.

Sau mốc đó, không sửa luật, ngưỡng, định nghĩa hay cách cài đặt nào dưới đây. Ngoại lệ duy nhất là các sửa đổi ở mục cuối, làm trước khi phiên đầu tiên của phép đo đóng cửa và chốt bằng tag `prereg/breadth-filter-amend1`, `prereg/breadth-filter-amend2` và `prereg/breadth-filter-amend3`. Phép đo chạy bằng code ở tag sửa đổi sau cùng.

## Giả thuyết

Khi VN-Index đang trên MA200, tín hiệu phá nền phát ra lúc cổng độ rộng đóng có lợi nhuận 40 phiên thấp hơn rõ rệt so với lúc cổng độ rộng mở. Nếu đúng, hệ thống nên bỏ các tín hiệu đó, nhưng không đóng danh mục và không đụng tới lệnh đang giữ.

Đây khác cổng độ rộng đã đo trong `breadth_gate.md`. Cổng đó đứng ngoài thị trường và bán cả rổ khi độ rộng đóng, nên tốn lợi nhuận trong các sóng tăng như 2021. Bộ lọc chỉ từ chối lệnh mua mới.

## Vì sao chốt luật này

Trên dữ liệu 2015–2026-10-09, đây là quy luật nhất quán nhất của báo cáo cổng độ rộng. Lợi nhuận TB 40 phiên của tín hiệu có MA200 mở, đo theo hai cách:

| Giai đoạn | Nhóm giữ (độ rộng mở): từ phiên tín hiệu → từ phiên sau | Nhóm bỏ (độ rộng đóng): từ phiên tín hiệu → từ phiên sau |
|---|---|---|
| Lùi 2015–2020 | +5.9% → +5.6% (133 tín hiệu) | +0.7% → +1.1% (69) |
| Chọn 2021–2024 | +4.3% → +5.0% (137) | −0.6% → −1.6% (22) |
| Xác nhận 2025–2026 | +6.6% → +4.4% (28) | −1.6% → −1.3% (34) |

Quy luật này được nhận ra *sau khi* đã xem cả ba giai đoạn, nên không giai đoạn nào trong bảng còn dùng được để kiểm tra nó. Phép đo dưới đây chỉ dùng các phiên chạy thật từ `BREADTH_FILTER_START` trở đi.

## Định nghĩa

| Mục | Định nghĩa |
|---|---|
| Dữ liệu | Các phiên từ `BREADTH_FILTER_START` (2026-10-13), tức phiên đóng cửa đầu tiên sau khi tag được push |
| Tín hiệu | Như `find_signals` trong `research/app/breadth_report.py`: một phiên một mã thuộc rổ 100 của năm (`pit_universe`) đạt `assess_pattern`. Không xét cổng cơ bản, tin tức hay dòng ngoại |
| MA200 mở | `market_regime` của VN-Index tới hết phiên tín hiệu cho `open` là True, như cột MA200 của báo cáo |
| Trạng thái độ rộng | Giá trị `BREADTH50_STATE` cuối cùng mà phiên chạy thật đã ghi cho chính phiên tín hiệu: 1 là mở, 0 là đóng. Không tính lại từ nến, vì cần đúng trạng thái hệ thống đã thấy |
| Mẫu đo | Tín hiệu có MA200 mở và có trạng thái độ rộng đã lưu |
| Nhóm giữ / nhóm bỏ | Tín hiệu lúc độ rộng mở / lúc độ rộng đóng |
| Lợi nhuận | Từ giá đóng cửa *phiên sau* phiên tín hiệu tới giá đóng cửa 40 phiên VN-Index sau đó (`BREADTH_FILTER_HORIZON`). Mỗi mốc lấy giá đóng cửa cuối cùng không muộn hơn mốc, nên mã ngừng giao dịch giữ giá cuối. Không trừ phí |
| Đã đủ phiên | Kho đã có phiên VN-Index thứ 41 sau phiên tín hiệu |

Lợi nhuận đo từ phiên sau vì kết luận "Được vào" chỉ có sau giờ đóng cửa. Không ai mua được ở giá đóng cửa của chính phiên tín hiệu, và bộ lọc đo bằng giá không mua được thì không đáng tin. Lựa chọn này vì lý do thực thi. Bảng trên cho thấy nó không lật kết quả lịch sử.

Tín hiệu phát ra ở phiên không có `BREADTH50_STATE` bị loại khỏi mẫu, và được đếm riêng. Lý do có thể là phiên chạy thật không chạy, chạy lỗi, hoặc độ rộng "chưa chấm". Không lấp trạng thái thiếu bằng số tính lại.

Định nghĩa tín hiệu, rổ, độ rộng và cách đo là bản ở tag. Mục 7.5 của báo cáo ưu tiên sửa điểm vào lệnh, nên `assess_pattern` có thể đổi trước lần đo. Khi đó, phép đo vẫn chạy bằng code ở tag (ví dụ `git worktree add ../prereg prereg/breadth-filter-amend3`).

## Luật qua cửa

Phải đạt cả hai điều kiện:

| # | Điều kiện | Ngưỡng | Hằng số |
|---|---|---|---|
| 1 | Mỗi nhóm có đủ tín hiệu đã đủ phiên và có giá | ≥ 30 | `BREADTH_FILTER_MIN_SIGNALS` |
| 2 | Lợi nhuận TB 40 phiên của nhóm giữ trừ nhóm bỏ | ≥ 2 điểm % | `BREADTH_FILTER_MIN_EDGE` |

Hai điều kiện này giống tầng tín hiệu của cổng độ rộng, để hai phép đo so được với nhau.

**Số báo cáo, không thuộc luật:** nhóm bỏ có lãi TB thấp hơn phí cả vòng 0.3% hay không. Bộ lọc chỉ thật sự có lợi khi các tín hiệu bị bỏ không đáng vào lệnh. Nhưng điều này không được làm điều kiện bắt buộc, vì ba lý do:

- lịch sử đã trượt nó: giai đoạn lùi có nhóm bỏ +0.7%;
- với 30 tín hiệu và độ lệch chuẩn 11–16%, sai số của trung bình nhóm bỏ khoảng ±2.5 điểm, lớn gấp nhiều lần khoảng cách tới 0.3%. Nếu trung bình thật là −1%, khả năng qua chỉ khoảng 70%. Ghép với điều kiện 2, một giả thuyết đúng bằng độ lớn lịch sử chỉ có khoảng một nửa cơ hội qua;
- lọc nhầm một nhóm lãi +1% thì thiệt rất ít so với cách biệt 5–8 điểm đang tìm.

Các ngưỡng là mức tối thiểu có ý nghĩa kinh tế, không phải kiểm định thống kê. Với 30 tín hiệu ở nhóm bỏ, sai số của cách biệt vào khoảng ±3–4 điểm, nên một cách biệt sát 2 điểm vẫn có thể là may. Số sát ngưỡng không phải lý do để nới ngưỡng.

## Thời điểm đo

- **Sớm nhất:** khi mỗi nhóm có ít nhất 30 tín hiệu đã đủ phiên, và đã qua ít nhất 12 tháng từ ngày bắt đầu (`BREADTH_FILTER_MIN_MONTHS`). Mười hai tháng để mẫu không chỉ đến từ một kiểu thị trường.
- **Chỉ đo một lần.** `python -m app.breadth_filter --measure` chỉ chạy khi đã đủ điều kiện hoặc đã quá hạn chót. Nó ghi `research/reports/breadth_filter.md` và từ chối chạy lại khi file đó đã có.
- **Trước lần đo, chỉ được xem số đếm** bằng `python -m app.breadth_filter`: số tín hiệu của mỗi nhóm, số đã đủ phiên, số bị loại, số phiên thiếu trạng thái. Không xem lợi nhuận, tỷ lệ thắng hay bất kỳ số nào suy ra kết quả.
- **Muộn nhất:** 60 tháng từ ngày bắt đầu (`BREADTH_FILTER_MAX_MONTHS`), tức 2031-10-13. Tới lúc đó mà một nhóm vẫn chưa đủ 30 tín hiệu thì kết luận "không đủ mẫu", và giả thuyết dừng lại.

**Ước lượng thời gian.** Nhóm hiếm là nhóm bỏ. Trong các tín hiệu có MA200 mở, nhóm bỏ mỗi năm có:

| 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 16 | 14 | 6 | 26 | 4 | 8 | 0 | 1 | 13 | 17 | 17 |

\* tới 2026-10-09.

Trung bình khoảng 10 tín hiệu mỗi năm, dao động từ 0 tới 26. Nhóm giữ trung bình khoảng 25 tín hiệu mỗi năm. Theo lịch sử, xét các cửa sổ tính từ đầu mỗi năm:

- **Cửa sổ 36 tháng:** 3 trên 10 cửa sổ không đủ 30 tín hiệu ở nhóm bỏ (bắt đầu 2020, 2021, 2022), và một cửa sổ chỉ có 31.
- **Cửa sổ 60 tháng:** 1 trên 8 cửa sổ không đủ (2020–2024, 26 tín hiệu).

Thời gian thường gặp là 2–4 năm. Khả năng kết thúc bằng "không đủ mẫu" khoảng 1/8.

## Kết quả và việc làm theo

**Nếu qua:** thêm cờ `BREADTH_SIGNAL_FILTER_ENFORCED` (hiện chưa có) và bật nó. Khi bật, ở phiên VN-Index trên MA200 mà độ rộng đóng, verdict lẽ ra là "Được vào" chuyển thành "Theo dõi", với lý do "Độ rộng đóng". Lệnh đang giữ, luật thoát lệnh và danh mục không đổi. Phiên độ rộng "chưa chấm" không bị chặn. Trang `/backtest` và sổ giấy áp cùng luật.

**Nếu không qua, hoặc không đủ mẫu:** độ rộng giữ vai trò quan sát như hiện tại. Không thử lại luật này trên cùng dữ liệu, không nới ngưỡng.

## Dữ liệu và rủi ro vận hành

- **Nến của mã rời rổ.** Phiên chạy thật chỉ nạp nến cho rổ 200 của năm hiện tại. Sang năm sau, mã rơi khỏi rổ sẽ ngừng được cập nhật, và lợi nhuận 40 phiên của tín hiệu cuối năm trước sẽ thành đi ngang giả. Vì vậy lệnh đo nạp lại nến của VN-Index và của mọi mã thuộc rổ 100 từ năm bắt đầu, *trước* khi tính.
- **Trạng thái tính từ nến chưa đóng.** Phiên chạy thật ghi `BREADTH50_STATE` cho phiên VN-Index mới nhất, và lần chạy sau ghi đè lần trước. Nếu bấm chạy trong giờ giao dịch mà sau đó không chạy lại sau giờ đóng cửa, trạng thái lưu được tính từ nến chưa đóng. Luật lấy giá trị cuối cùng đã ghi, như đã định nghĩa ở trên.
- **Chưa có lịch chạy cố định.** Phiên chạy thật chỉ khởi động bằng `POST /run`. Ngày nào không chạy sau giờ đóng cửa thì phiên đó không có trạng thái độ rộng, và mọi tín hiệu của phiên đó bị loại. Lệnh đếm in số phiên thiếu trạng thái để theo dõi điều này. Muốn mẫu đủ nhanh và không lệch theo ngày chạy, cần một lịch chạy cố định sau giờ đóng cửa.

## Giới hạn đã biết

- **Tín hiệu không độc lập.** Trên lịch sử, khoảng 18% tín hiệu là cùng một mã phát lại trong vòng 40 phiên. Tín hiệu cũng dồn theo từng đợt thị trường: nhóm bỏ của giai đoạn chọn chỉ rơi vào 8 tháng. Vì thế 30 tín hiệu chứa ít thông tin độc lập hơn con số 30, và sai số thật lớn hơn ước lượng ở trên.
- **Tập đo khác tập áp dụng.** Phép đo chạy trên rổ 100 theo năm và không xét các cổng khác. Còn luật "Theo dõi", khi bật, áp lên kết luận của danh sách theo dõi (`DEFAULT_UNIVERSE`, 106 mã cố định) sau khi đã qua cổng vĩ mô, cổng tiền tệ và dòng ngoại. Hai tập này khác nhau, giống điểm đã ghi cho cổng ngành ở `docs/industry-first-backlog.md`.

## Những gì không thuộc phép đo này

- **Không đổi cổng độ rộng:** MA50, mốc 55/45/50%, 30 mã hợp lệ, 5 phiên nến cũ giữ nguyên. Giả thuyết 7.4.3 (vùng đệm rộng hơn hoặc N phiên liên tiếp) là luật khác. Nó đổi chính trạng thái mà phép đo này đọc, nên không chạy song song.
- **Không đo giả thuyết 7.4.2** (siết dừng lỗ khi độ rộng đóng) trên cùng dữ liệu.
- **Đo lại cổng cứng (mục 7.2 của báo cáo)** đã được duyệt cùng ngày, như một phép đo riêng với luật riêng. Nó dùng cùng các phiên chạy thật nhưng trả lời câu hỏi khác: có nên đứng ngoài thị trường hay không. Không phép nào là lần thử lại của phép kia, và kết quả của phép này không đổi luật của phép kia.
- **Sổ lệnh không nằm trong luật qua cửa,** vì số lệnh mỗi năm quá ít.

## Sửa đổi trước phiên đầu

Làm ngày 2026-10-12, sau tag `prereg/breadth-filter` và trước khi phiên 2026-10-13 đóng cửa, tức khi chưa có phiên nào của phép đo. Chốt bằng tag `prereg/breadth-filter-amend1`. Sửa đổi không đổi mẫu đo, cách chia nhóm, cách tính lợi nhuận hay luật qua cửa.

1. **Dừng đo khi nạp lại nến lỗi.** Ở bản đầu, nếu nạp lại nến của một mã lỗi, lệnh đo chỉ ghi cảnh báo rồi vẫn tính và ghi báo cáo. Lợi nhuận của mã đó khi ấy tính từ nến cũ, thành đi ngang giả, đúng lỗi mà bước nạp lại được thêm vào để chặn. Nay `refresh_bars` trả danh sách mã mà cả Entrade lẫn bảng giá VNDirect đều không trả nến. Nếu có mã nào trong đó có tín hiệu đã đủ phiên trong mẫu, lệnh đo dừng *trước khi* ghi báo cáo, nên lượt đo một lần chưa bị dùng mất; chạy lại khi nguồn trả đủ nến.
2. **Câu hiển thị trước phiên đầu.** Khi kho chưa có phiên nào từ ngày bắt đầu, lệnh đếm in "chưa có phiên nào" thay vì một khoảng ngày bị đảo.

Ngày bắt đầu giữ 2026-10-13. Tag đầu đã lên GitHub trước giờ đóng cửa ngày 2026-10-12, nên phiên đó cũng đã đủ điều kiện; giữ 2026-10-13 chỉ thận trọng hơn một phiên, và cũng là phiên đầu tiên đóng cửa sau tag sửa đổi.

### Sửa đổi thứ hai

Làm trước khi phiên 2026-10-13 đóng cửa, khi kho chưa có phiên nào của phép đo. Chốt bằng tag `prereg/breadth-filter-amend2`. Sửa đổi này thay mục 1 ở trên, và cũng không đổi mẫu đo, cách chia nhóm, cách tính lợi nhuận hay luật qua cửa.

1. **Chỉ chặn tín hiệu không xác nhận được nến.** Bản sửa đổi đầu chặn mọi mã nạp lại lỗi, kể cả khi nến đã lưu trong kho đủ để tính lợi nhuận, nên một nguồn lỗi lâu dài có thể chặn lệnh đo mãi. Nó cũng bỏ sót mã đã vào mẫu nhưng không có trong danh sách nạp lại: danh sách ấy lập từ rổ tính trên nến *trước khi* nạp lại, còn mẫu lập từ rổ tính trên nến *sau khi* nạp lại. Nay mỗi tín hiệu đã đủ phiên và có nhóm phải xác nhận được nến bằng một trong ba cách:
   - mã vừa nạp lại thành công;
   - nến lưu trong kho đã tới phiên bán (phiên VN-Index thứ 41 sau phiên tín hiệu);
   - mã đã hủy niêm yết không muộn hơn phiên bán, và nến lưu cách ngày hủy không quá `BREADTH_MAX_STALE_SESSIONS` (5) phiên VN-Index.

   Còn tín hiệu không xác nhận được thì lệnh đo dừng *trước khi* ghi báo cáo, và in mã cần nạp lại.
2. **Hạn chót.** Khi đã quá 60 tháng mà vẫn còn tín hiệu không xác nhận được nến, các tín hiệu đó tính là thiếu giá: bị loại khỏi nhóm, như tín hiệu không có giá trong kho, và được liệt kê trong báo cáo. Sau đó kết luận như thường, nên nếu một nhóm còn dưới 30 tín hiệu có giá thì kết luận "không đủ mẫu".
3. **Báo cáo ghi mốc chốt và code đã chạy.** Đầu báo cáo nêu tag gốc và cả hai tag sửa đổi, kèm kết quả `git describe` của code chạy phép đo.

### Sửa đổi thứ ba

Làm ngày 2026-10-12, trước khi phiên 2026-10-13 đóng cửa, khi kho vẫn chưa có phiên nào của phép đo. Chốt bằng tag `prereg/breadth-filter-amend3`. Sửa đổi này thay mục 1 và mục 2 của sửa đổi thứ hai ở phần *làm gì với tín hiệu không xác nhận được nến*. Cách xác nhận nến giữ nguyên.

Sửa đổi thứ hai ghi rằng nó không đổi mẫu đo. Điều đó chưa hoàn toàn đúng. Ở bản đó, trước hạn chót chỉ một tín hiệu không xác nhận được nến cũng chặn cả lệnh đo. Ví dụ: một mã tạm ngừng giao dịch nhiều tháng rồi mới hủy niêm yết, và cả hai nguồn đều không trả nến. Khi đó lệnh đo có thể bị dời tới tận tháng 60, trừ khi bổ sung nến bằng tay. Trong lúc chờ, mẫu vẫn lớn thêm, nên thời điểm đo, và qua đó cả mẫu đo, phụ thuộc vào một lỗi dữ liệu.

1. **Tín hiệu không xác nhận được nến tính là thiếu giá ngay, không chờ hạn chót.** Chúng bị loại khỏi nhóm và được liệt kê trong báo cáo.
2. **Điều kiện "sớm nhất" đếm tín hiệu có giá.** Mỗi nhóm phải có ít nhất 30 tín hiệu đã đủ phiên *và có giá*, sau khi đã loại tín hiệu thiếu giá. Lệnh đếm vẫn in số đã đủ phiên như cũ. Khi chạy, lệnh đo nạp lại nến, xác nhận nến, rồi xét lại điều kiện này. Nếu chưa đạt thì lệnh dừng mà không ghi báo cáo, và chạy lại khi mẫu lớn thêm hoặc khi nguồn trả đủ nến. Tới hạn chót thì kết luận như thường, nên kết luận là "không đủ mẫu" nếu một nhóm còn dưới 30 tín hiệu có giá.
3. **Số thiếu giá luôn được đếm.** Ở bản trước, khi đã quá hạn chót mà chưa đủ mẫu, báo cáo in "thiếu giá: 0" nhưng ngay sau đó lại liệt kê tín hiệu "trong đó tính là thiếu giá". Nay số thiếu giá được đếm trong mọi trường hợp, nên luôn khớp với danh sách.

Cái giá của cách này: tín hiệu của mã ngừng giao dịch rồi hủy niêm yết thường là tín hiệu xấu, nên nếu nến của chúng không xác nhận được, việc loại chúng có thể làm nhóm của chúng trông tốt hơn thực tế. Rủi ro này đã có từ trước: chặn tới hạn chót rồi cũng loại các tín hiệu ấy. Báo cáo liệt kê từng tín hiệu bị loại, nên vẫn kiểm tra lại được bằng tay. Rổ 100 toàn mã thanh khoản cao, nên trường hợp này hiếm. Trên dữ liệu từ 2024, cả 100 tín hiệu đã đủ phiên đều xác nhận được nến mà không cần nạp lại.
