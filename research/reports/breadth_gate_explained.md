# Cổng độ rộng — báo cáo giải thích

Bản này giải thích `breadth_gate.md` cho người chưa theo dõi quá trình làm: thuật ngữ, cách làm phép thử,
ý nghĩa từng bảng và từng cột, những gì học được, và khuyến nghị.

`breadth_gate.md` do `app/breadth_report.py` sinh tự động và bị ghi đè mỗi lần chạy. Bản này viết tay, đọc
kèm số của lần chạy ngày 2026-10-12, với nến tới hết phiên 2026-10-09. Chạy lại báo cáo thì số có thể lệch
nhẹ, và phần diễn giải ở đây cần đọc lại.

**Mục lục**

1. Tóm tắt
2. Bối cảnh
3. Thuật ngữ
4. Cách làm phép thử
5. Đọc từng bảng của `breadth_gate.md`
6. Tổng hợp: học được gì, và giới hạn của phép đo
7. Khuyến nghị
8. Chạy lại và file liên quan

---

## 1. Tóm tắt

**Câu hỏi.** Hệ thống hiện chỉ cho mua mới khi VN-Index đóng cửa trên MA200. Nếu thêm điều kiện "đa số cổ
phiếu đang khỏe", tức độ rộng thị trường, thì hệ thống có tốt hơn không?

**Kết luận theo luật đã chốt: chưa qua.** Cờ `BREADTH_GATE_ENFORCED` giữ tắt. Regime chính thức vẫn là
VN-Index trên MA200, cộng cổng vĩ mô và cổng tiền tệ.

**Ba chỗ trượt:**

| # | Giai đoạn | Điều kiện | Kết quả | Ngưỡng |
|---|---|---|---|---|
| 1 | Chọn 2021–2024 | Sụt sâu nhất nông hơn | 17.9% | ≥ 20% |
| 2 | Chọn 2021–2024 | Lợi nhuận mỗi năm kém đi | 4.9 điểm % | ≤ 1 điểm % |
| 3 | Xác nhận 2025–2026 | Số tín hiệu lúc độ rộng mở | 28 | ≥ 30 |

Các điều kiện còn lại đều đạt, và đạt rõ:

- Tín hiệu lúc độ rộng mở tốt hơn lúc đóng 8.2 điểm ở giai đoạn chọn và 8.6 điểm ở giai đoạn xác nhận,
  so với ngưỡng 2 điểm.
- Ở giai đoạn xác nhận, mức sụt nông hơn 60.7%, và lợi nhuận mỗi năm *tốt hơn* 12.8 điểm.

**Độ rộng có giá trị thông tin thật:**

- Ở 2021–2026, tín hiệu phá nền phát ra khi độ rộng đóng có lợi nhuận 40 phiên trung vị khoảng −5%, và chỉ
  khoảng 1/3 số tín hiệu có lãi.
- Năm 2026 (tới 09/10), VN-Index nằm trên MA200 80% số phiên nhưng độ rộng chỉ mở 9%. Danh mục chỉ dùng
  MA200 mất 18.7%, còn danh mục có thêm độ rộng chỉ mất 3.2%.

**Vì sao vẫn chưa qua.** Năm 2021 là sóng tăng lan rộng nhưng có những nhịp điều chỉnh sâu. Trong năm đó độ
rộng đóng cổng khoảng 19% số phiên và bỏ lỡ các nhịp hồi: danh mục có độ rộng chỉ lãi +40.6%, so với +74.1%
của MA200. Lợi ích của cổng không ổn định giữa các kiểu thị trường.

**Khuyến nghị ngắn:**

- Giữ độ rộng ở vai trò quan sát: lưu mỗi phiên, hiện trên `/market`, có trong mỗi verdict.
- Không nới ngưỡng, không dựng máy nhiều trạng thái.
- Đo lại theo đúng luật cũ khi dữ liệu chạy thật đủ mẫu.

---

## 2. Bối cảnh

### 2.1 Cổng thị trường hiện tại

Trước báo cáo này, cổng thị trường theo giá chỉ có một điều kiện: **VN-Index đóng cửa trên MA200**.

- Khi cổng đóng, mọi mã chuyển sang "Khóa" và không có lệnh mua mới. Lệnh đang giữ vẫn quản lý theo luật thoát riêng.
- Cổng này đứng cạnh cổng vĩ mô (DXY, tỷ giá, S&P 500, dầu) và cổng tiền tệ (lãi suất, tỷ giá liên ngân hàng).
  Các cổng nối với nhau theo kiểu AND: tất cả cùng mở thì mới mua.

### 2.2 Điểm yếu của MA200 trên VN-Index

- **VN-Index tính theo vốn hóa.** Vài mã rất lớn như nhóm Vingroup hay ngân hàng lớn có thể đẩy chỉ số lên trên
  MA200 trong khi phần lớn cổ phiếu khác đang giảm. Hệ thống khi đó vẫn mở cửa mua, dù môi trường cho cú phá nền
  của số đông cổ phiếu là xấu.
- **MA200 chậm.** Sau các đáy lớn, nó cần 99–132 phiên mới mở lại (mục 5.8).

### 2.3 Đề xuất và phạm vi phép thử

Đề xuất là thêm **độ rộng thị trường**: đếm xem bao nhiêu cổ phiếu đang khỏe, thay vì chỉ nhìn chỉ số.

Các đề xuất khác được thảo luận nhưng **không đưa vào phép thử**: máy 4–5 trạng thái, ADX dưới 20 coi là
"sideway", "mua tỷ trọng nhỏ trong sóng hồi", "bắt đáy hoảng loạn". Lý do:

- mỗi trạng thái kéo theo một chiến lược mới chưa có trong hệ thống;
- thêm nhiều tham số thì dễ khớp quá mức với dữ liệu quá khứ;
- trường hợp đáy hoảng loạn chỉ có hai mẫu trong 12 năm.

Bảng bốn ô ở mục 5.6 dùng để kiểm tra các ý tưởng đó bằng dữ liệu, nhưng chỉ để chẩn đoán, không phải luật.

---

## 3. Thuật ngữ

### 3.1 Giá và đường trung bình

- **Phiên:** một ngày giao dịch. "40 phiên" là 40 ngày giao dịch, khoảng 2 tháng lịch.
- **MA50, MA200:** trung bình cộng giá đóng cửa của 50 hoặc 200 phiên gần nhất, tính cả phiên đang xét.
  "Giá trên MA50" nghĩa là giá đóng cửa hôm nay cao hơn trung bình 50 phiên gần nhất.
- **Giá đã điều chỉnh (`close`):**
  - giá được nguồn dữ liệu tính lùi sau chia tách, thưởng cổ phiếu và cổ tức, để chuỗi giá liền mạch;
  - ví dụ một mã chia tách 1:2 thì giá trước ngày chia tách được chia đôi;
  - mọi tín hiệu và độ rộng đều dùng giá này.
- **Giá thật (`raw_close`):** giá khớp thực tế của phiên. Chỉ dùng để tính vốn hóa khi chốt rổ, vì số cổ phiếu
  lưu hành là số của chính thời điểm đó.
- **Biên độ sàn:** mức tăng hoặc giảm tối đa một phiên, là HOSE ±7%, HNX ±10%, UPCoM ±15%. Hệ thống dùng mốc
  rộng hơn để tránh báo nhầm: 9%, 12% và 17% (`PRICE_JUMP_LIMITS`). Đây cũng là mốc mà bộ quét dùng để nhận
  ra mã chưa chỉnh chia tách.
- **Bước gãy điều chỉnh:**
  - một phiên mà giá đã điều chỉnh nhảy quá biên độ sàn;
  - giá thật không thể làm điều đó, nên đây là dấu hiệu nguồn dữ liệu áp hệ số chia tách sai ngày;
  - ví dụ TV2 ngày 2021-07-15: giá đã điều chỉnh +26% trong khi giá thật −0.9%;
  - nếu không xử lý, MA50 của mã sẽ sai suốt 50 phiên sau đó.

### 3.2 Rổ cổ phiếu theo thời điểm

- **Rổ theo thời điểm (point-in-time):** rổ được dựng lại cho từng năm, chỉ bằng thông tin có tại thời điểm đó.
  Ở phiên giao dịch đầu năm, hệ thống:
  1. lấy mọi mã đang niêm yết trên HOSE và HNX tại phiên đó, kể cả mã về sau hủy niêm yết;
  2. tính vốn hóa bằng giá thật của phiên nhân số cổ phiếu đã công bố ít nhất 45 ngày;
  3. loại mã có giá trị khớp trung vị 20 phiên trước đó dưới 3 tỷ đồng;
  4. xếp theo vốn hóa từ lớn xuống nhỏ.
- **Rổ 200:** 200 mã đầu danh sách. Dùng để tính độ rộng.
- **Rổ 100:** 100 mã đầu danh sách. Là nơi được phát tín hiệu và vào lệnh.
- **Thiên lệch sống sót:** lỗi khi chỉ kiểm thử trên các mã còn sống tới hôm nay. Những mã đó, theo định nghĩa,
  là mã đã không phá sản, nên kết quả kiểm thử đẹp hơn thực tế. Rổ theo thời điểm giữ cả 95 mã đã hủy niêm yết
  trong những năm chúng còn giao dịch.

### 3.3 Độ rộng và cổng

- **Độ rộng:** tỷ lệ mã của rổ 200 có giá đóng cửa trên MA50 của chính nó, tính trên số mã hợp lệ. Phiên
  2026-10-09 có 58 trên 186 mã hợp lệ nằm trên MA50, nên độ rộng là 31.2%.
- **Mã hợp lệ:** mã được đưa vào phép đếm của một phiên. Mã bị loại khi rơi vào một trong ba trường hợp:

  | Lý do loại | Điều kiện | Vì sao |
  |---|---|---|
  | Nến cũ | Nến cuối của mã cách phiên đang chấm quá 5 phiên | Mã tạm ngừng giao dịch giữ mãi giá cũ, không phản ánh thị trường |
  | Thiếu nến | Chưa đủ 50 nến | Chưa tính được MA50 |
  | Có bước gãy | Trong 50 nến gần nhất có một bước gãy điều chỉnh | MA50 bị sai do dữ liệu |

- **Cổng:** một điều kiện có ba trạng thái:
  - **mở**: được mua mới;
  - **đóng**: không mua mới;
  - **chưa chấm**: không đủ dữ liệu. Với độ rộng, đó là khi có dưới 30 mã hợp lệ.
- **Cổng AND:** mọi cổng cùng mở thì mới được mua. "MA200 và độ rộng" nghĩa là VN-Index trên MA200 *và* cổng
  độ rộng đang mở.
- **Độ trễ hai ngưỡng (hysteresis):** cổng dùng hai mốc thay vì một mốc 50%:
  - từ 55% trở lên thì mở;
  - từ 45% trở xuống thì đóng;
  - ở giữa (45–55%) giữ nguyên trạng thái phiên trước;
  - phiên đầu tiên chấm được chưa có trạng thái trước, nên lấy mốc 50%.

  Ví dụ:

  | Phiên | Độ rộng | Trạng thái | Giải thích |
  |---|---|---|---|
  | 1 | 40% | đóng | phiên đầu: 40% < 50% |
  | 2 | 54% | đóng | trong vùng 45–55%: giữ trạng thái trước |
  | 3 | 55% | **mở** | chạm mốc mở |
  | 4 | 46% | mở | trong vùng giữa: giữ trạng thái trước |
  | 5 | 45% | **đóng** | chạm mốc đóng |
  | 6 | 50% | đóng | trong vùng giữa: giữ trạng thái trước |

  Nếu chỉ dùng một mốc 50%, chuỗi trên sẽ đổi trạng thái ở các phiên 2, 4, 5, 6. Độ trễ hai ngưỡng chỉ đổi ở
  phiên 3 và 5.
- **Số lần đổi trạng thái:** số lần cổng chuyển từ mở sang đóng hoặc ngược lại trong một giai đoạn. Càng ít thì
  cổng càng ổn định, và danh mục càng ít bị mua đi bán lại.

### 3.4 Giai đoạn đo

| Giai đoạn | Khoảng thời gian | Vai trò | Vì sao |
|---|---|---|---|
| Chọn (in-sample) | 2021-01-04 → 2024-12-31 | Giai đoạn chính, nằm trong luật qua cửa | Rổ đủ 200 mã và số cổ phiếu lưu hành đầy đủ từ 2021 |
| Xác nhận (out-of-sample) | 2025-01-01 → 2026-10-09 | Kiểm tra lại, nằm trong luật qua cửa | Xem kết quả có lặp lại trên dữ liệu khác không |
| Lùi | 2015-01-01 → 2020-12-31 | Chỉ để đối chiếu | Rổ chỉ 62–118 mã; sổ lệnh chỉ chấm được cơ bản từ 2018-02-15 |

### 3.5 Thước đo

- **Danh mục chia đều:**
  - khi cổng mở, mỗi phiên cầm đều tỷ trọng mọi mã của rổ 100;
  - khi cổng đóng, đứng tiền và hưởng lãi 5.5%/năm;
  - phí 0.3% cả vòng (0.15% mỗi chiều), tính trên phần tỷ trọng đổi chủ.

  Đây là cách đo giá trị của bản thân cổng: không có chọn mã, không có dừng lỗ, chỉ có "vào thị trường hay
  đứng ngoài".
- **Lợi nhuận (cả giai đoạn):** đường vốn cuối kỳ chia đầu kỳ, trừ 1.
- **Lợi nhuận mỗi năm (CAGR):** lợi nhuận kép quy về một năm, để so được các giai đoạn dài ngắn khác nhau.
  Ví dụ +53.2% trong 4 năm tương đương khoảng +11.3% mỗi năm.
- **Sụt sâu nhất (max drawdown):** mức giảm lớn nhất từ một đỉnh của đường vốn xuống đáy sau đó. −16.1% nghĩa
  là có lúc danh mục mất 16.1% so với đỉnh gần nhất. Con số này đo nỗi đau lớn nhất mà người cầm danh mục
  phải chịu.
- **"Nông hơn X%":** so sánh tương đối giữa hai mức sụt, bằng 1 − (sụt có cổng ÷ sụt không cổng). Ví dụ
  1 − 13.2/16.1 ≈ 18%. Dùng tỷ lệ tương đối để so được giữa giai đoạn sụt nhiều và giai đoạn sụt ít.
- **Điểm %:** hiệu số giữa hai tỷ lệ phần trăm. Từ 16.2% xuống 11.3% là kém 4.9 điểm %, không phải kém 4.9%.
- **Tín hiệu phá nền:** một phiên một mã thuộc rổ 100 đạt đủ điều kiện của `assess_pattern`:
  1. 10 phiên gần nhất có biên độ trung bình hẹp hơn 10 phiên trước đó (siết biên độ);
  2. khối lượng 10 phiên gần nhất thấp hơn 10 phiên trước đó (cạn cung);
  3. giá đóng cửa vượt đỉnh cao nhất của 20 phiên nền;
  4. khối lượng phiên phá nền ít nhất 1.5 lần trung bình 20 phiên nền;
  5. nền không sâu quá 15%, tính từ đỉnh xuống đáy nền;
  6. có nhịp tăng ít nhất 15% trong 40 phiên trước nền;
  7. lợi nhuận 60 phiên của mã cao hơn VN-Index (sức mạnh tương đối dương);
  8. không có cú phá nền thất bại gần đây, và chuỗi giá không có bước gãy chưa chỉnh chia tách.

  Đây là điều kiện kỹ thuật mà hệ thống dùng để vào lệnh, *chưa* tính lọc cơ bản, tin tức và dòng tiền ngoại.
- **Lợi nhuận 20/40/60 phiên:**
  - đo từ giá đóng cửa phiên tín hiệu tới giá đóng cửa cuối cùng không muộn hơn phiên thứ 20/40/60 sau đó
    theo lịch VN-Index;
  - mã ngừng giao dịch hay hủy niêm yết giữa chừng giữ giá cuối của nó, không bị bỏ khỏi mẫu;
  - không trừ phí.
- **Trung bình và trung vị:**
  - trung bình là tổng chia số tín hiệu;
  - trung vị là giá trị đứng giữa khi xếp các tín hiệu theo lợi nhuận;
  - lợi nhuận cổ phiếu lệch phải (vài tín hiệu lãi rất lớn), nên trung vị thường thấp hơn trung bình. Trung vị
    cho biết một tín hiệu "điển hình" ra sao.
- **Tỷ lệ thắng:** phần trăm tín hiệu có lợi nhuận 40 phiên lớn hơn 0.
- **Độ lệch chuẩn và sai số chuẩn:**
  - lợi nhuận 40 phiên của từng tín hiệu dao động rất mạnh, độ lệch chuẩn khoảng 12–20%;
  - sai số chuẩn của số trung bình bằng độ lệch chuẩn chia căn bậc hai số tín hiệu;
  - với 30 tín hiệu và độ lệch chuẩn 16%, sai số khoảng 16/√30 ≈ 2.9 điểm %. Tức là trung bình của 30 tín
    hiệu có thể lệch khoảng ±3 điểm chỉ vì may rủi.
- **Sổ lệnh:** mô phỏng đầy đủ hệ thống:
  - 5 suất vốn, mỗi lệnh rủi ro 1% vốn chủ;
  - dừng lỗ ở đáy nền, chốt 1/3 vị thế ở +1R, sau đó kéo dừng lỗ theo MA20;
  - đóng khi tiền chết 30 phiên, khi có công bố chặn, khi dòng tiền ngoại đảo chiều, hoặc khi giá đóng cửa
    trở lại dưới đỉnh nền đã phá;
  - áp đủ cổng cơ bản (báo cáo tài chính dùng sau 45 ngày kết thúc kỳ), tin tức và dòng tiền ngoại.
- **R:** khoảng cách từ giá vào tới dừng lỗ. +1R nghĩa là lãi bằng đúng mức rủi ro ban đầu.
- **ADX (Average Directional Index):** chỉ báo đo độ mạnh của xu hướng trong 14 phiên, bất kể hướng lên hay
  xuống. Thường đọc trên 25 là xu hướng mạnh, dưới 20 là đi ngang. Ở đây chỉ là cột mô tả, không phải cổng.

### 3.6 Kỷ luật đo

- **Chốt trước (pre-registration):** ngưỡng và luật qua cửa được ghi vào `config.py` trước lần chạy đầu, và
  không sửa sau khi đã xem kết quả.
- **Nhìn trộm dữ liệu (data snooping):**
  - thử nhiều phiên bản trên cùng dữ liệu rồi chọn phiên bản đẹp nhất;
  - phiên bản được chọn trông tốt một phần vì may, nên thường không lặp lại trong tương lai;
  - "không nới ngưỡng sau khi đã xem số" là để tránh lỗi này.
- **Dữ liệu sạch:** dữ liệu chưa ai dùng để chọn luật. Một khi đã xem kết quả của một giai đoạn, giai đoạn đó
  không còn sạch cho các biến thể mới.

---

## 4. Cách làm phép thử

### 4.1 Nguyên tắc

1. **Chốt luật trước khi đo.**
   - Ngày 2026-10-12, trước lần chạy đầu, các hằng số `BREADTH_*` được ghi vào `config.py`: MA50, mốc 55/45/50%,
     tối thiểu 30 mã, nến không cũ quá 5 phiên, và toàn bộ luật qua cửa.
   - Lượt khảo sát dữ liệu trước đó chỉ kiểm tra chất lượng dữ liệu: thiếu nến, khối lượng 0, bước gãy giá.
     Lượt đó không tính độ rộng và không nhìn lợi nhuận.
2. **Phải qua ở cả hai giai đoạn.** Qua giai đoạn chọn mà trượt giai đoạn xác nhận, hoặc ngược lại, đều tính là
   chưa qua. Một luật chỉ đúng ở một giai đoạn có thể chỉ là may.
3. **Không nới ngưỡng.** Số sát ngưỡng như 17.9% so với 20% không phải lý do để hạ ngưỡng. Đổi luật là một phép
   thử mới, phải đo trên dữ liệu chưa từng xem.
4. **Chỉ so ba biến thể khai báo trước:**
   - MA200 đơn thuần, là mốc so sánh;
   - độ rộng đơn thuần, để tham khảo;
   - MA200 và độ rộng, là biến thể được xét qua cửa.

   Không quét thêm cửa sổ MA20/MA100/MA200 cho độ rộng, cũng không thử ngưỡng khác. Mỗi lần thử thêm làm tăng
   khả năng tìm ra một kết quả đẹp do may.

### 4.2 Dữ liệu

| Mục | Giá trị |
|---|---|
| Nến ngày | 2014-01-02 → 2026-10-09; 764 mã, gồm 95 mã đã hủy niêm yết |
| Nguồn giá | Entrade (DNSE) cho mã còn niêm yết, bảng giá VNDirect cho mã đã hủy niêm yết; giá thật và giá trị khớp nạp riêng bằng `history_pull --raw-tape` |
| Rổ 200 theo năm | 62–118 mã (2014–2020), 174–200 mã (2021–2026) |
| Sàn trong rổ | khoảng 86% HOSE, 14% HNX |
| Chất lượng trong rổ | thiếu nến dưới 1% số phiên; không có phiên khối lượng 0 |
| Bước gãy điều chỉnh | 12 trường hợp trong rổ đúng năm đó (mục 5.2) |
| Bảng sàn cho sổ lệnh | `backend/data/vstock.db`, để áp đúng luật giá chưa chỉnh chia tách |

### 4.3 Tính độ rộng từng phiên

**Các bước**, lặp lại cho mỗi phiên giao dịch của VN-Index:

1. Lấy rổ 200 của năm chứa phiên đó. Nếu phiên nằm trước phiên chốt rổ đầu năm thì dùng rổ năm trước.
2. Với từng mã trong rổ:
   - nến cuối của mã cách phiên đang chấm quá 5 phiên → loại, tính là **nến cũ**;
   - chưa đủ 50 nến → loại, tính là **thiếu nến**;
   - cửa sổ 50 nến gần nhất có bước gãy điều chỉnh → loại, tính là **có bước gãy**. Bước gãy ở nến j so sánh
     nến j với nến j−1, nên nó chỉ nằm trong cửa sổ khi cả hai nến đều thuộc cửa sổ;
   - còn lại là **mã hợp lệ**: so giá đóng cửa với MA50.
3. Độ rộng = số mã hợp lệ trên MA50 ÷ số mã hợp lệ. Dưới 30 mã hợp lệ thì phiên đó chưa chấm.
4. Chuyển tỷ lệ thành trạng thái bằng độ trễ hai ngưỡng. Phiên chưa chấm có trạng thái "chưa chấm", nhưng
   không xóa trạng thái trước đó: phiên chấm được tiếp theo vẫn so với mốc 55% và 45% như thường.

**Ví dụ thật: phiên 2026-10-09.**

| Bước | Số |
|---|---|
| Rổ 200 của năm 2026 | 187 mã (rổ có ít hơn 200 mã vì chỉ 187 mã qua ngưỡng thanh khoản ở phiên chốt rổ) |
| Loại vì nến cũ | 0 |
| Loại vì thiếu nến | 0 |
| Loại vì có bước gãy | 1 (AGG, bước gãy ngày 2026-08-28) |
| Mã hợp lệ | 186 |
| Mã trên MA50 | 58 |
| Độ rộng | 58 ÷ 186 = 31.2% |
| Trạng thái | đóng: 31.2% thấp hơn 45%, nên dù phiên trước mở hay đóng thì hôm nay cũng đóng |

### 4.4 Ba tầng đo, và vì sao cần cả ba

Mỗi tầng trả lời một câu hỏi khác nhau, và mỗi tầng đều có điểm mù riêng.

**Tầng thị trường**
- *Câu hỏi:* bản thân cổng có giúp né thua lỗ mà không bỏ lỡ quá nhiều lợi nhuận không?
- *Cách đo:* danh mục chia đều rổ 100, chỉ cầm khi cổng mở. So ba biến thể với nhau, và với VN-Index cùng "Cả rổ".
- *Điểm mạnh:* đo đúng cái cổng làm, là quyết định vào thị trường hay đứng ngoài, không lẫn với chất lượng chọn mã.
- *Điểm mù:* hệ thống thật không cầm cả rổ. Mức sụt sâu nhất do một đợt sụt duy nhất quyết định, nên nhạy với may rủi.

**Tầng tín hiệu**
- *Câu hỏi:* khi độ rộng đóng, các cú phá nền có thất bại nhiều hơn không?
- *Cách đo:* lợi nhuận 40 phiên của mọi tín hiệu phá nền trong rổ 100, tách theo trạng thái độ rộng ở phiên tín hiệu.
- *Điểm mạnh:* kiểm tra đúng điểm vào lệnh của hệ thống. Mẫu lớn hơn sổ lệnh nhiều: 224 so với 79 ở giai đoạn chọn.
- *Điểm mù:* chưa trừ phí, chưa qua cổng cơ bản, tin tức, dòng tiền ngoại. Các tín hiệu cùng thời điểm thường
  tương quan với nhau, nên số tín hiệu "độc lập" thực ra ít hơn số đếm.

**Sổ lệnh**
- *Câu hỏi:* toàn bộ hệ thống, gồm cổng, chọn mã, dừng lỗ và thoát lệnh, có tốt hơn khi thêm cổng không?
- *Cách đo:* `run_backtest` có và không có cổng độ rộng, trên mọi mã từng vào rổ 200.
- *Điểm mạnh:* gần với thực tế nhất.
- *Điểm mù:* chỉ có 19–79 lệnh mỗi giai đoạn, quá ít để phân biệt khác biệt thật với may rủi. Vì vậy chỉ để
  tham khảo, không nằm trong luật qua cửa.

Kết hợp lại: tầng thị trường đo giá trị phòng thủ của cổng, tầng tín hiệu đo khả năng phân loại tín hiệu tốt
và xấu, còn sổ lệnh kiểm tra xem hai điều đó có thể hiện trong hệ thống thật không.

### 4.5 Chống nhìn trước tương lai

Mọi quyết định trong phép thử chỉ dùng thông tin đã có tại thời điểm quyết định:

| Thành phần | Thông tin dùng | Ghi chú |
|---|---|---|
| Rổ năm | Giá thật của phiên chốt rổ; số cổ phiếu đã công bố ít nhất 45 ngày; thanh khoản 20 phiên trước phiên chốt; trạng thái niêm yết tại phiên chốt | Rổ không biết mã nào sẽ tăng, giảm hay hủy niêm yết về sau |
| Độ rộng của phiên d | Giá đóng cửa tới hết phiên d | MA50 và bước gãy chỉ xét các nến không muộn hơn d |
| Trạng thái cổng | Chuỗi độ rộng tới hết phiên d | Độ trễ hai ngưỡng chỉ nhìn về quá khứ |
| MA200 của phiên d | Giá đóng cửa VN-Index tới hết phiên d | Giống cổng đang chạy thật |
| Danh mục chia đều, cột chính | Trạng thái cổng ở phiên d quyết định việc cầm từ giá đóng cửa phiên d tới phiên d+1 | Tức mua ngay giá đóng cửa của phiên vừa có tín hiệu. Đây cũng là quy ước của sổ lệnh hiện tại |
| Danh mục chia đều, cột "trễ 1 phiên" | Trạng thái ở phiên d quyết định việc cầm từ phiên d+1 tới d+2 | Mua ở giá đóng cửa phiên sau. Thận trọng hơn |
| Tín hiệu | Nến tới hết phiên d; lợi nhuận đo từ giá đóng cửa phiên d | Tín hiệu chưa đủ 40 phiên tới cuối kho thì không có số 40 phiên, chứ không bị điền bằng giá hiện tại |
| Sổ lệnh | Báo cáo tài chính dùng sau 45 ngày kết thúc kỳ | Đồng hồ tin tức bỏ qua vì tin cũ không được lưu đủ lâu |

**Giá đã điều chỉnh có làm lộ tương lai không?** Hệ số điều chỉnh do nguồn tính sau này, nhưng nó nhân cả chuỗi
với cùng một hệ số. Phép so "giá trên MA50" không đổi khi cả giá và MA50 cùng nhân một số. Trường hợp duy nhất
gây sai là hệ số áp sai ngày, tức bước gãy điều chỉnh, và trường hợp đó đã bị loại khỏi phép đếm.

**Mua ở giá đóng cửa phiên tín hiệu có thực tế không?** Phiên hằng ngày chạy sau giờ đóng cửa, nên thực tế
thường mua ở phiên sau. Vì vậy cột chính hơi lạc quan, và cột "trễ 1 phiên" là con số thận trọng. Kết luận
"chưa qua" đúng với cả hai cột (mục 5.4).

### 4.6 Luật qua cửa và ý nghĩa từng ngưỡng

Phải đạt **cả hai tầng**, ở **cả giai đoạn chọn lẫn xác nhận**.

**Tầng thị trường** (so "MA200 và độ rộng" với "MA200"):

| Ngưỡng | Ý nghĩa | Vì sao chọn mức này |
|---|---|---|
| Sụt sâu nhất nông hơn ít nhất 20% (tương đối) | Cổng phải giảm rõ rệt nỗi đau lớn nhất | Mức sụt do một đợt quyết định nên rất nhiễu; cải thiện dưới 20% (ví dụ −16% thành −13%) khó phân biệt với may. Dùng tỷ lệ tương đối để so được giữa giai đoạn sụt nhiều và sụt ít |
| Lợi nhuận mỗi năm không kém quá 1 điểm % | Cái giá của sự an toàn phải nhỏ | Một cổng phòng thủ giống mua bảo hiểm. Nếu phí bảo hiểm vượt 1 điểm mỗi năm, khoảng 1/5 lãi tiền gửi 5.5%, thì lợi ích giảm sụt không bù được |

**Tầng tín hiệu:**

| Ngưỡng | Ý nghĩa | Vì sao chọn mức này |
|---|---|---|
| Lợi nhuận TB 40 phiên lúc mở cao hơn lúc đóng ít nhất 2 điểm % | Độ rộng phải tách được tín hiệu tốt và xấu | 40 phiên nằm giữa khung giữ lệnh 30–60 phiên của hệ thống. 2 điểm gấp khoảng 7 lần phí cả vòng 0.3%, là khác biệt có ý nghĩa kinh tế |
| Mỗi phía ít nhất 30 tín hiệu đã đủ 40 phiên | Số trung bình không bị vài tín hiệu chi phối | Với độ lệch chuẩn khoảng 16%, 30 tín hiệu cho sai số khoảng ±3 điểm. Ít hơn thì trung bình dao động quá mạnh |

**Lưu ý quan trọng:** đây là ngưỡng *tối thiểu* về ý nghĩa kinh tế, không phải kiểm định thống kê.

- Với 30 tín hiệu mỗi phía, sai số của hiệu hai trung bình khoảng ±4 điểm. Một cách biệt đúng 2 điểm vẫn có
  thể là may.
- Cách biệt thực tế đo được lớn hơn nhiều:
  - giai đoạn chọn: 8.2 điểm, sai số khoảng 2.3 điểm, tức khoảng 3.6 lần sai số;
  - giai đoạn xác nhận: 8.6 điểm, sai số khoảng 3.8 điểm, tức khoảng 2.2 lần sai số.

**Vì sao giai đoạn lùi không nằm trong luật:** rổ những năm đó nhỏ (62–118 mã), nên mỗi mã chiếm 1–1.6% độ rộng.
Sổ lệnh cũng chưa có số liệu cơ bản trước 2018-02-15.

---

## 5. Đọc từng bảng của `breadth_gate.md`

Mỗi bảng dưới đây chép lại đúng bảng trong `breadth_gate.md`, giải thích từng cột, rồi diễn giải.

### 5.1 Bảng kết luận

| Giai đoạn | Sụt sâu nhất nông hơn | Lợi nhuận mỗi năm kém | Tín hiệu mở − đóng (40 phiên) | Tín hiệu mở / đóng |
|---|---|---|---|---|
| Chọn | 17.9% | +4.9% | +8.2% | 182 / 42 |
| Xác nhận | 60.7% | -12.8% | +8.6% | 28 / 31 |

**Từng cột:**

- **Sụt sâu nhất nông hơn:** 1 − (sụt của "MA200 và độ rộng" ÷ sụt của "MA200"), dùng cột chính của tầng thị
  trường. Cần ≥ 20%.
  - Chọn: 1 − 13.2/16.1 = 17.9%, trượt.
  - Xác nhận: 1 − 9.7/24.7 = 60.7%, đạt.
- **Lợi nhuận mỗi năm kém:** lợi nhuận mỗi năm của "MA200" trừ của "MA200 và độ rộng". Cần ≤ +1 điểm.
  - Số dương là có cổng *kém hơn*. Chọn: 16.2% − 11.3% = +4.9 điểm, trượt.
  - Số âm là có cổng *tốt hơn*. Xác nhận: −1.9% − 10.9% = −12.8 điểm, đạt rất rõ.
- **Tín hiệu mở − đóng (40 phiên):** lợi nhuận trung bình 40 phiên của tín hiệu lúc độ rộng mở trừ lúc đóng.
  Đây là hiệu số tính bằng điểm %, dù bảng ghi dấu "%". Cần ≥ +2 điểm. Cả hai giai đoạn đều đạt.
- **Tín hiệu mở / đóng:** số tín hiệu mỗi phía *đã đủ 40 phiên*. Cần ≥ 30 mỗi phía.
  - Xác nhận: phía mở chỉ có 28, nên tính là chưa đủ mẫu.
  - Phía đóng ghi 31, trong khi bảng tầng tín hiệu ghi 37. Lý do: 6 tín hiệu cuối, phát ra trong 40 phiên cuối
    của kho dữ liệu, chưa có kết quả 40 phiên nên không được tính ở đây.
  - Phía mở của giai đoạn xác nhận ghi 28 ở cả hai bảng, tức cả 28 tín hiệu mở đều đã đủ 40 phiên.

**Diễn giải:**

- Độ rộng tách tín hiệu tốt và xấu rất rõ ở cả hai giai đoạn.
- Như một cổng chặn cứng, nó thắng lớn ở giai đoạn xác nhận nhưng thua ở giai đoạn chọn.
- Luật yêu cầu đạt ở cả hai, nên kết luận là chưa qua.

### 5.2 Bảng dữ liệu

| Năm | Rổ | Mã đếm TB | Nến cũ TB | Thiếu nến TB | Có bước gãy TB | Phiên chưa chấm |
|---|---|---|---|---|---|---|
| 2014 | 62 | 50 | 0.0 | 11.3 | 0.0 | 49 |
| 2015 | 76 | 76 | 0.0 | 0.0 | 0.0 | 0 |
| 2016 | 75 | 75 | 0.0 | 0.1 | 0.0 | 0 |
| 2017 | 74 | 73 | 0.3 | 0.2 | 0.0 | 0 |
| 2018 | 118 | 118 | 0.0 | 0.3 | 0.0 | 0 |
| 2019 | 100 | 100 | 0.0 | 0.1 | 0.0 | 0 |
| 2020 | 102 | 102 | 0.0 | 0.0 | 0.1 | 0 |
| 2021 | 200 | 199 | 0.0 | 0.1 | 1.0 | 0 |
| 2022 | 200 | 198 | 1.1 | 0.1 | 0.4 | 0 |
| 2023 | 174 | 173 | 0.3 | 0.0 | 0.4 | 0 |
| 2024 | 191 | 190 | 0.5 | 0.0 | 0.2 | 0 |
| 2025 | 200 | 200 | 0.0 | 0.0 | 0.0 | 0 |
| 2026 | 187 | 186 | 0.0 | 0.4 | 0.3 | 0 |

**Từng cột:**

- **Rổ:** số mã của rổ 200 năm đó. Năm nào có ít hơn 200 mã là vì chỉ chừng đó mã có vốn hóa và qua ngưỡng
  thanh khoản tại phiên chốt rổ.
- **Mã đếm TB:** số mã hợp lệ trung bình mỗi phiên trong năm.
- **Nến cũ TB, Thiếu nến TB, Có bước gãy TB:** số mã trung bình mỗi phiên bị loại theo từng lý do (mục 3.3).
- **Phiên chưa chấm:** số phiên có dưới 30 mã hợp lệ.

**Diễn giải:**

- Mã đếm gần bằng kích thước rổ ở mọi năm, tức gần như không mã nào bị loại. Độ rộng phản ánh đúng rổ.
- Năm 2014 có 49 phiên chưa chấm và trung bình 11.3 mã thiếu nến. Lý do: kho bắt đầu từ 2014-01-02, nên tới
  2014-03-21 đa số mã mới đủ 50 nến. Năm 2014 không thuộc phép đo nào.
- Năm 2022 có trung bình 1.1 mã nến cũ, là các mã bị tạm ngừng giao dịch trong năm.

**Danh sách 12 bước gãy điều chỉnh**, chỉ tính mã nằm trong rổ đúng năm đó: APH 2021-07-14, AAA 2021-08-27,
TV2 2021-07-15 và 2021-07-16, TDP 2021-07-15, TVC 2021-07-15, APH 2022-01-24, TVB 2022-08-03, DXS 2023-08-18,
PET 2023-04-10, HPX 2024-03-20, AGG 2026-08-28.

- Phần lớn là lỗi hệ số chia tách của nguồn: giá đã điều chỉnh nhảy mạnh trong khi giá thật gần như đứng yên.
- HPX 2024-03-20 là phiên giao dịch lại sau 6 tháng ngừng, khi giá thật cũng tăng 20%.
- **Giới hạn:** sàn của mỗi mã lấy theo bảng niêm yết hiện tại. Mã từng ở HNX rồi chuyển sang HOSE bị xét theo
  mốc 9% của HOSE, nên một phiên tăng 10% hợp lệ khi còn ở HNX có thể bị đánh dấu nhầm. Hậu quả chỉ là mã đó
  bị loại 50 nến, không làm sai tỷ lệ của các mã còn lại.

### 5.3 Trạng thái cổng

| Giai đoạn | Cổng | Tỷ lệ phiên mở | Số lần đổi trạng thái | Độ rộng TB |
|---|---|---|---|---|
| Lùi | MA200 | 61.4% | 35 |  |
| Lùi | Độ rộng | 40.5% | 39 | 47.4% |
| Lùi | MA200 và độ rộng | 32.6% | 33 |  |
| Chọn | MA200 | 64.7% | 20 |  |
| Chọn | Độ rộng | 56.2% | 36 | 53.2% |
| Chọn | MA200 và độ rộng | 44.0% | 30 |  |
| Xác nhận | MA200 | 83.1% | 21 |  |
| Xác nhận | Độ rộng | 30.4% | 13 | 44.1% |
| Xác nhận | MA200 và độ rộng | 30.1% | 13 |  |

**Từng cột:**

- **Tỷ lệ phiên mở:** phần trăm số phiên cổng mở trong giai đoạn, không tính phiên chưa chấm. Đây là thời gian
  hệ thống được phép mua mới.
- **Số lần đổi trạng thái:** số lần chuyển giữa mở và đóng. Mỗi lần đổi là một lần danh mục phải mua vào hoặc
  bán ra toàn bộ.
- **Độ rộng TB:** độ rộng trung bình của các phiên trong giai đoạn. Chỉ ghi ở dòng "Độ rộng".

**Diễn giải:**

- **Giai đoạn xác nhận:** VN-Index trên MA200 tới 83% số phiên nhưng độ rộng chỉ mở 30%, với độ rộng trung bình
  44%. Đây là bằng chứng định lượng cho hiện tượng vài mã trụ kéo chỉ số trong khi số đông cổ phiếu yếu.
- **Độ trễ hai ngưỡng chưa làm độ rộng ổn định hơn MA200.** Ở giai đoạn chọn, độ rộng đổi trạng thái 36 lần
  (khoảng 9 lần mỗi năm), so với 20 lần của MA200. Lý do là độ rộng biến động rất mạnh: năm 2021 dao động từ 22%
  tới 98%, năm 2023 từ 5% tới 92% (mục 5.4). Vùng đệm 10 điểm (45–55%) là quá hẹp so với biên độ đó.
- **Cổng AND luôn làm giảm thời gian được mua.** Ở giai đoạn chọn, thời gian được mua giảm từ 64.7% xuống 44.0%.
  Đây là cái giá mặc định của mọi cổng thêm vào, và là lý do chính khiến lợi nhuận năm 2021 giảm.

### 5.4 Tầng thị trường

| Danh mục | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lợi nhuận trễ 1 phiên | Sụt sâu nhất trễ 1 phiên |
|---|---|---|---|---|---|---|
| VN-Index | Lùi | +102.3% | +12.5% | -45.3% | — | — |
| Cả rổ | Lùi | +17.4% | +2.7% | -47.4% | — | — |
| MA200 | Lùi | +21.2% | +3.3% | -26.8% | +16.9% | -25.7% |
| Độ rộng | Lùi | +70.1% | +9.3% | -10.3% | +56.8% | -11.0% |
| MA200 và độ rộng | Lùi | +65.4% | +8.8% | -7.3% | +51.5% | -11.0% |
| VN-Index | Chọn | +14.8% | +3.5% | -40.3% | — | — |
| Cả rổ | Chọn | +57.8% | +12.1% | -53.4% | — | — |
| MA200 | Chọn | +82.0% | +16.2% | -16.1% | +85.6% | -15.9% |
| Độ rộng | Chọn | +29.7% | +6.7% | -24.3% | +31.2% | -21.4% |
| MA200 và độ rộng | Chọn | +53.2% | +11.3% | -13.2% | +40.1% | -13.0% |
| VN-Index | Xác nhận | +37.0% | +19.5% | -18.1% | — | — |
| Cả rổ | Xác nhận | +9.9% | +5.5% | -21.0% | — | — |
| MA200 | Xác nhận | -3.4% | -1.9% | -24.7% | -5.8% | -24.2% |
| Độ rộng | Xác nhận | +18.4% | +10.0% | -9.7% | +15.6% | -9.7% |
| MA200 và độ rộng | Xác nhận | +20.0% | +10.9% | -9.7% | +16.2% | -9.7% |

**Từng dòng (danh mục):**

- **VN-Index:** chỉ số giá, tính theo vốn hóa, không có phí. Mốc tham chiếu của thị trường.
- **Cả rổ:** luôn cầm đều rổ 100, không có cổng. Cho biết thị trường "số đông" tăng giảm ra sao.
- **MA200, Độ rộng, MA200 và độ rộng:** cầm đều rổ 100 khi cổng tương ứng mở, đứng tiền khi đóng.

**Từng cột:**

- **Lợi nhuận, Mỗi năm, Sụt sâu nhất:** xem mục 3.5. Đây là cột chính, mua ở giá đóng cửa phiên có tín hiệu.
- **Lợi nhuận trễ 1 phiên, Sụt sâu nhất trễ 1 phiên:** cùng danh mục, nhưng mua và bán chậm một phiên. VN-Index
  và "Cả rổ" không có cổng nên không có cột này.

**"Cả rổ" so với VN-Index.** Hai cách đo khác nhau: rổ chia đều cho 100 mã, chỉ số đặt tỷ trọng theo vốn hóa.

- Giai đoạn chọn: rổ (+57.8%) thắng chỉ số (+14.8%), vì cổ phiếu vừa và nhỏ tăng rất mạnh năm 2021.
- Giai đoạn xác nhận: ngược lại, rổ chỉ +9.9% trong khi chỉ số +37%. Đợt tăng 2025–2026 tập trung vào vài mã vốn
  hóa lớn.
- Chính bối cảnh "chỉ số tăng nhưng số đông không tăng" này là lúc độ rộng phát huy tác dụng.

**Cột trễ 1 phiên.** Các biến thể có độ rộng nhạy với độ trễ hơn MA200, vì độ rộng đổi trạng thái thường xuyên
hơn:

| Giai đoạn | MA200 và độ rộng: cột chính | Cột trễ 1 phiên | MA200: cột chính | Cột trễ 1 phiên |
|---|---|---|---|---|
| Chọn | +53.2% | +40.1% | +82.0% | +85.6% |
| Xác nhận | +20.0% | +16.2% | −3.4% | −5.8% |

- Ở cột trễ, khoảng cách lợi nhuận giữa hai biến thể ở giai đoạn chọn còn lớn hơn cột chính.
- Mức sụt ở cột trễ cũng chỉ nông hơn khoảng 18% (−13.0% so với −15.9%), vẫn dưới ngưỡng 20%.
- Vậy kết luận "chưa qua" đúng với cả hai cột. Nếu thực tế mua ở phiên sau, cổng độ rộng còn kém hơn ở giai
  đoạn chọn.

**Phân rã theo năm.** Bảng này không có trong `breadth_gate.md`; nó được tính riêng bằng cùng các hàm, cột chính.

| Năm | VN-Index | Cả rổ | MA200 | MA200 và độ rộng | Tỷ lệ phiên MA200 mở | Tỷ lệ phiên độ rộng mở | Độ rộng TB (thấp nhất – cao nhất) |
|---|---|---|---|---|---|---|---|
| 2015 | +6.1% | −9.9% | −5.5% | +0.8% | 42% | 33% | 41% (4–80%) |
| 2016 | +14.8% | −9.8% | −13.4% | +4.6% | 73% | 42% | 46% (13–75%) |
| 2017 | +48.0% | +28.5% | +28.5% | +6.1% | 100% | 58% | 56% (26–79%) |
| 2018 | −9.3% | −15.1% | −13.5% | +6.4% | 44% | 23% | 41% (6–88%) |
| 2019 | +7.7% | +2.4% | −5.0% | +2.8% | 72% | 36% | 46% (19–88%) |
| 2020 | +14.9% | +29.4% | +40.1% | +35.3% | 37% | 50% | 54% (2–97%) |
| 2021 | +35.7% | +74.1% | **+74.1%** | **+40.6%** | 100% | 81% | 70% (22–98%) |
| 2022 | −32.8% | −39.6% | −2.7% | −0.4% | 28% | 30% | 34% (1–87%) |
| 2023 | +12.2% | +37.0% | +7.4% | +11.0% | 43% | 64% | 60% (5–92%) |
| 2024 | +12.1% | +9.6% | +0.1% | −1.4% | 90% | 51% | 50% (7–86%) |
| 2025 | +40.9% | +23.3% | +18.9% | +24.1% | 86% | 47% | 51% (5–95%) |
| 2026* | −2.8% | −10.9% | **−18.7%** | **−3.2%** | 80% | 9% | 34% (11–65%) |

\* tới 2026-10-09.

**Diễn giải theo năm:**

- **2021 quyết định kết quả của giai đoạn chọn.**
  - VN-Index trên MA200 suốt cả năm, nên danh mục MA200 cầm rổ trọn sóng tăng +74.1%.
  - Độ rộng có những nhịp tụt xuống tới 22%, đóng cổng khoảng 19% số phiên, và bỏ lỡ các nhịp hồi mạnh sau đó.
  - Lợi nhuận gần như chỉ còn một nửa: +40.6%.
- **2022–2024:** có thêm độ rộng ngang hoặc tốt hơn ở 2022 (−0.4% so với −2.7%) và 2023 (+11.0% so với +7.4%),
  kém nhẹ ở 2024 (−1.4% so với +0.1%).
- **2025–2026 là giai đoạn độ rộng phát huy rõ nhất.** Năm 2026, VN-Index trên MA200 80% số phiên nhưng độ rộng
  chỉ mở 9%: danh mục MA200 mất 18.7%, có thêm độ rộng chỉ mất 3.2%.
- **2015–2019 (giai đoạn lùi):** có thêm độ rộng tốt hơn ở 4 trên 5 năm. Ngoại lệ là 2017, năm sóng tăng lớn,
  độ rộng lại bỏ lỡ (+6.1% so với +28.5%). Đây là cùng một kiểu thất bại như 2021.

**Vì sao mức sụt chỉ cải thiện 17.9% ở giai đoạn chọn.** Mức sụt sâu nhất của hai biến thể rơi vào hai đợt khác nhau:

- MA200: 2023-09-12 → 2024-08-08, sụt −16.1%;
- MA200 và độ rộng: 2024-04-02 → 2024-12-24, sụt −13.2%.

Độ rộng né được đợt sụt 2023–2024 của MA200, nhưng tự gặp một đợt sụt khác cuối năm 2024. Đây là ví dụ cho việc
mức sụt sâu nhất do một đợt duy nhất quyết định nên rất nhiễu.

**Tóm lại cho tầng thị trường:** độ rộng là cổng phòng thủ tốt khi thị trường hẹp (2022, 2026) hoặc đi ngang
(2015–2019). Nhưng nó gây thiệt hại lớn trong các sóng tăng lan rộng có nhịp điều chỉnh sâu (2017, 2021). Lợi hay
hại phụ thuộc vào kiểu thị trường, chưa đủ ổn định để thành luật cứng.

### 5.5 Tầng tín hiệu

| Giai đoạn | Nhóm | Tín hiệu | TB 20 phiên | TB 40 phiên | Trung vị 40 | Thắng 40 | TB 60 phiên |
|---|---|---|---|---|---|---|---|
| Lùi | Tất cả | 312 | +2.5% | +3.9% | +1.5% | 53.5% | +6.9% |
| Lùi | Độ rộng mở | 186 | +2.4% | +3.5% | +2.6% | 54.3% | +8.0% |
| Lùi | Độ rộng đóng | 126 | +2.8% | +4.3% | +0.8% | 52.4% | +5.3% |
| Lùi | MA200 mở, độ rộng mở | 133 | +2.9% | +5.9% | +4.0% | 59.4% | +11.0% |
| Lùi | MA200 mở, độ rộng đóng | 69 | +0.4% | +0.7% | -0.4% | 47.8% | +1.3% |
| Chọn | Tất cả | 224 | +1.0% | +2.3% | +1.3% | 54.0% | +3.9% |
| Chọn | Độ rộng mở | 182 | +1.8% | +3.9% | +1.8% | 59.3% | +5.8% |
| Chọn | Độ rộng đóng | 42 | -2.4% | -4.3% | -5.6% | 31.0% | -4.3% |
| Chọn | MA200 mở, độ rộng mở | 137 | +2.5% | +4.3% | +1.6% | 56.2% | +5.9% |
| Chọn | MA200 mở, độ rộng đóng | 22 | +0.2% | -0.6% | -4.2% | 40.9% | +2.9% |
| Xác nhận | Tất cả | 65 | +0.6% | +2.1% | -2.4% | 47.5% | +1.7% |
| Xác nhận | Độ rộng mở | 28 | +2.4% | +6.6% | +4.6% | 57.1% | +3.7% |
| Xác nhận | Độ rộng đóng | 37 | -1.0% | -1.9% | -5.0% | 38.7% | -0.2% |
| Xác nhận | MA200 mở, độ rộng mở | 28 | +2.4% | +6.6% | +4.6% | 57.1% | +3.7% |
| Xác nhận | MA200 mở, độ rộng đóng | 34 | -0.9% | -1.6% | -4.8% | 40.0% | -0.2% |

**Từng nhóm:**

- **Tất cả:** mọi tín hiệu trong giai đoạn.
- **Độ rộng mở / đóng:** tách theo trạng thái độ rộng ở phiên tín hiệu. Đây là hai nhóm mà luật qua cửa so sánh.
- **MA200 mở, độ rộng mở / đóng:** chỉ xét tín hiệu phát ra khi VN-Index trên MA200, tức những tín hiệu mà hệ
  thống hiện tại vẫn cho mua. Hai nhóm này chỉ để tham khảo.

**Từng cột:**

- **Tín hiệu:** số tín hiệu của nhóm, kể cả tín hiệu chưa đủ 40 hay 60 phiên.
- **TB 20 / 40 / 60 phiên:** lợi nhuận trung bình sau 20/40/60 phiên, chỉ tính các tín hiệu đã đủ số phiên đó.
- **Trung vị 40:** lợi nhuận 40 phiên của tín hiệu đứng giữa.
- **Thắng 40:** phần trăm tín hiệu có lãi sau 40 phiên.

Vì các cột TB chỉ tính tín hiệu đã đủ phiên, ở giai đoạn xác nhận cột "Tín hiệu" có thể lớn hơn số dùng cho cột
TB 40. Ví dụ nhóm độ rộng đóng ghi 37 tín hiệu nhưng TB 40 tính trên 31.

**Diễn giải:**

- **Ở 2021–2026, tín hiệu lúc độ rộng đóng là tín hiệu xấu ở mọi khung thời gian.** Ở giai đoạn chọn: TB 20
  phiên −2.4%, TB 40 phiên −4.3%, TB 60 phiên −4.3%, trung vị 40 phiên −5.6%, chỉ 31% có lãi. Giai đoạn xác
  nhận tương tự: trung vị −5.0%, 38.7% có lãi.
- **Tín hiệu lúc độ rộng mở có lãi ở mọi khung,** với tỷ lệ thắng 57–59%.
- **Cách biệt đủ lớn so với độ nhiễu.** Ở giai đoạn chọn, cách biệt 8.2 điểm bằng khoảng 3.6 lần sai số
  (mục 4.6), khó là may. Ở giai đoạn xác nhận, cách biệt 8.6 điểm bằng khoảng 2.2 lần sai số, kém chắc hơn vì
  mẫu nhỏ.
- **Giai đoạn lùi không có cách biệt.** Nhóm độ rộng đóng còn cao hơn nhóm mở 0.8 điểm. Nguyên nhân nằm ở bảng
  bốn ô (mục 5.6): các cú phá nền khi thị trường đang dưới MA200 và độ rộng đóng của 2015–2020 lãi trung bình
  +8.7%. Đó là những cú bật sau các đáy, như sau cú sập tháng 3/2020.
- **Khi chỉ xét phiên MA200 mở, độ rộng tách tín hiệu ở cả ba giai đoạn:**

  | Giai đoạn | MA200 mở, độ rộng mở | MA200 mở, độ rộng đóng | Cách biệt |
  |---|---|---|---|
  | Lùi | +5.9% (133 tín hiệu) | +0.7% (69) | +5.2 điểm |
  | Chọn | +4.3% (137) | −0.6% (22) | +4.9 điểm |
  | Xác nhận | +6.6% (28) | −1.6% (34) | +8.2 điểm |

  Đây là quy luật nhất quán nhất của báo cáo. Nhưng nó được phát hiện *sau khi* đã xem số, và không phải luật đã
  chốt, nên chỉ là giả thuyết cho phép thử sau (mục 7.4).
- **Lưu ý:** lợi nhuận chưa trừ phí 0.3% cả vòng, và tín hiệu chưa qua cổng cơ bản, tin tức, dòng tiền ngoại.
  Đây là chất lượng của mô hình giá, không phải của lệnh thực tế.

### 5.6 Bốn ô MA200 × độ rộng

| Giai đoạn | Ô | Tỷ lệ phiên | ADX TB | Phiên ADX < 20 | Tín hiệu | TB 40 phiên | Thắng 40 | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| Lùi | Trên MA200, độ rộng mở | 32.6% | 28 | 20.3% | 133 | +5.9% | 59.4% |  |
| Lùi | Trên MA200, độ rộng đóng | 28.8% | 23 | 43.1% | 69 | +0.7% | 47.8% |  |
| Lùi | Dưới MA200, độ rộng mở | 8.0% | 21 | 51.7% | 53 | -2.4% | 41.5% |  |
| Lùi | Dưới MA200, độ rộng đóng | 30.7% | 30 | 18.2% | 57 | +8.7% | 57.9% |  |
| Chọn | Trên MA200, độ rộng mở | 44.0% | 25 | 42.1% | 137 | +4.3% | 56.2% |  |
| Chọn | Trên MA200, độ rộng đóng | 20.7% | 23 | 48.3% | 22 | -0.6% | 40.9% | chưa đủ mẫu |
| Chọn | Dưới MA200, độ rộng mở | 12.1% | 19 | 62.2% | 45 | +2.4% | 68.9% |  |
| Chọn | Dưới MA200, độ rộng đóng | 23.1% | 36 | 24.2% | 20 | -8.4% | 20.0% | chưa đủ mẫu |
| Xác nhận | Trên MA200, độ rộng mở | 30.1% | 29 | 31.8% | 28 | +6.6% | 57.1% | chưa đủ mẫu |
| Xác nhận | Trên MA200, độ rộng đóng | 53.0% | 23 | 25.4% | 34 | -1.6% | 40.0% |  |
| Xác nhận | Dưới MA200, độ rộng mở | 0.2% | 13 | 100.0% | 0 | — | — | chưa đủ mẫu |
| Xác nhận | Dưới MA200, độ rộng đóng | 16.7% | 28 | 24.7% | 3 | -12.6% | 0.0% | chưa đủ mẫu |

**Bảng này để làm gì.** Đây là bảng chẩn đoán, không phải luật. Bốn ô tương ứng với các trạng thái được nêu khi
thảo luận:

| Ô | Tên gọi khi thảo luận |
|---|---|
| Trên MA200, độ rộng mở | "Bull trend", xu hướng tăng lan rộng |
| Trên MA200, độ rộng đóng | "Distribution", phân phối: chỉ số khỏe nhưng số đông yếu |
| Dưới MA200, độ rộng mở | "Bear rally", sóng hồi trong thị trường gấu |
| Dưới MA200, độ rộng đóng | "Bear trend", thị trường gấu |

**Từng cột:**

- **Tỷ lệ phiên:** phần trăm số phiên của giai đoạn rơi vào ô đó. Bốn ô của một giai đoạn cộng lại là 100%.
- **ADX TB:** ADX 14 phiên trung bình của VN-Index trong các phiên thuộc ô.
- **Phiên ADX < 20:** phần trăm số phiên trong ô có ADX dưới 20, tức "đi ngang" theo cách đọc thông thường.
- **Tín hiệu, TB 40 phiên, Thắng 40:** như bảng tầng tín hiệu, cho các tín hiệu phát ra trong ô.
- **Ghi chú:** "chưa đủ mẫu" khi ô có dưới 30 tín hiệu đã đủ 40 phiên. Số của ô đó không nên dùng để kết luận.

**Diễn giải:**

- **"Bull trend" tốt ổn định ở cả ba giai đoạn,** với lợi nhuận 40 phiên +4.3% đến +6.6% và tỷ lệ thắng 56–59%.
  Đây đúng là ô mà cổng "MA200 và độ rộng" cho phép mua.
- **"Distribution" yếu ở cả ba giai đoạn,** từ +0.7% đến −1.6%, với tỷ lệ thắng 40–48%. Điều này ủng hộ ý tưởng
  không mua khi chỉ số khỏe mà số đông yếu. Ở giai đoạn xác nhận, đây là ô chiếm nhiều thời gian nhất (53%).
- **"Bear rally" đổi dấu:** +2.4% ở giai đoạn chọn nhưng −2.4% ở giai đoạn lùi. Không có cơ sở cho luật "mua tỷ
  trọng nhỏ trong sóng hồi".
- **"Bear trend" đổi dấu mạnh:** −8.4% ở giai đoạn chọn, +8.7% ở giai đoạn lùi. Mua phá nền trong thị trường gấu
  phụ thuộc vào từng đợt.
- **ADX không giúp phân loại:**
  - Ở giai đoạn lùi và chọn, ADX trung bình cao nhất lại rơi vào ô "Bear trend" (30 và 36), vì xu hướng giảm
    mạnh cũng là xu hướng mạnh.
  - Ô có nhiều phiên ADX < 20 nhất là "Bear rally" (51.7% và 62.2%). Ô này có kết quả đổi dấu giữa hai giai
    đoạn, nên ADX < 20 không báo trước kết quả xấu một cách nhất quán.
  - Đề xuất "ADX < 20 thì tắt bộ quét phá nền" không có cơ sở trong dữ liệu này.

### 5.7 Sổ lệnh

| Sổ | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lệnh vào | Thắng | Lãi TB mỗi lệnh |
|---|---|---|---|---|---|---|---|
| MA200 | Lùi | +21.7% | +7.1% | -1.8% | 30 | 30.0% | +2.3% |
| MA200 và độ rộng | Lùi | +22.0% | +7.2% | -2.1% | 22 | 36.4% | +4.1% |
| MA200 | Chọn | +16.5% | +3.9% | -4.1% | 79 | 21.5% | -0.5% |
| MA200 và độ rộng | Chọn | +19.2% | +4.5% | -3.3% | 68 | 23.5% | -0.2% |
| MA200 | Xác nhận | +4.8% | +2.7% | -4.1% | 37 | 27.0% | -0.6% |
| MA200 và độ rộng | Xác nhận | +8.6% | +4.8% | -3.2% | 19 | 31.6% | +0.5% |

**Từng cột:**

- **Lợi nhuận, Mỗi năm, Sụt sâu nhất:** của toàn bộ đường vốn, gồm cả lãi tiền gửi trên phần tiền đứng ngoài.
  Giai đoạn lùi tính từ 2018-02-15.
- **Lệnh vào:** số lệnh mở trong giai đoạn, tính theo ngày vào lệnh.
- **Thắng:** phần trăm lệnh đóng có lãi.
- **Lãi TB mỗi lệnh:** lợi nhuận trung bình mỗi lệnh, tính trên vốn của lệnh đó, không phải trên tổng vốn.

**Mốc so sánh "chỉ gửi tiền"** (lãi 5.5%/năm, lấy từ `industry_sweep.md`): lùi +16.5%, chọn +23.8%, xác nhận +9.9%.

**Diễn giải:**

- **Có cổng thì tốt hơn một chút ở cả ba giai đoạn:** lợi nhuận cao hơn, sụt nông hơn ở giai đoạn chọn và xác
  nhận, lãi TB mỗi lệnh cao hơn. Nhưng với 19–79 lệnh, chênh lệch nằm trong vùng may rủi.
- **Mức sụt rất nhỏ (−2% đến −4%)** vì mỗi lệnh chỉ rủi ro 1% vốn, và sổ đứng tiền phần lớn thời gian.
- **Tỷ lệ thắng thấp (21–36%)** là bình thường với kiểu giao dịch theo xu hướng có dừng lỗ chặt: nhiều lệnh lỗ
  nhỏ, ít lệnh lãi lớn. Hệ thống chỉ có lãi khi các lệnh lãi đủ lớn để bù.
- **Điểm quan trọng nhất của bảng này:** ở giai đoạn chọn và xác nhận, sổ không cổng có lãi TB mỗi lệnh âm, và
  tổng lợi nhuận (+16.5%, +4.8%) thấp hơn chỉ gửi tiền (+23.8%, +9.9%). Ngay cả khi có thêm cổng, sổ vẫn thua
  gửi tiền. Một cổng thị trường chỉ chọn *lúc nào* được mua. Nó không biến một điểm vào có kỳ vọng âm thành dương.

### 5.8 Độ trễ sau đáy

| Đỉnh | Đáy | Giảm | Cổng | Mở lại | Sau | VN-Index đã tăng từ đáy |
|---|---|---|---|---|---|---|
| 2018-04-09 | 2020-03-24 | -45.3% | MA200 | 2020-08-31 | 99 phiên | +33.7% |
| 2018-04-09 | 2020-03-24 | -45.3% | Độ rộng | 2020-05-06 | 28 phiên | +18.7% |
| 2018-04-09 | 2020-03-24 | -45.3% | MA200 và độ rộng | 2020-08-31 | 99 phiên | +33.7% |
| 2022-01-06 | 2022-11-15 | -40.3% | MA200 | 2023-06-01 | 132 phiên | +18.3% |
| 2022-01-06 | 2022-11-15 | -40.3% | Độ rộng | 2022-12-05 | 14 phiên | +19.9% |
| 2022-01-06 | 2022-11-15 | -40.3% | MA200 và độ rộng | 2023-06-01 | 132 phiên | +18.3% |

**Từng cột:**

- **Đỉnh, Đáy, Giảm:** một đợt VN-Index giảm ít nhất 20% từ đỉnh. Đáy là điểm thấp nhất trước khi chỉ số lập
  đỉnh mới. Chỉ có hai đợt như vậy từ 2014.
- **Cổng, Mở lại:** phiên đầu tiên sau đáy mà cổng mở.
- **Sau:** số phiên từ đáy tới phiên cổng mở lại.
- **VN-Index đã tăng từ đáy:** chỉ số đã tăng bao nhiêu tính tới phiên cổng mở lại, tức phần sóng hồi mà cổng
  bỏ lỡ.

**Diễn giải:**

- **Độ rộng hồi phục sớm hơn MA200 rất nhiều:** 14–28 phiên so với 99–132 phiên. Nhưng cổng AND phải chờ MA200,
  nên mở lại cùng lúc với MA200.
- **Mở sớm không có nghĩa là bắt được nhiều sóng hơn.** Năm 2022, độ rộng mở lại sau 14 phiên khi chỉ số đã tăng
  +19.9%, nhiều hơn mức +18.3% khi MA200 mở lại sau 132 phiên. Lý do: chỉ số hồi rất nhanh rồi đi ngang suốt
  nửa đầu 2023.
- **Chỉ có hai mẫu trong 12 năm.** Mọi luật bắt đáy dựng trên hai mẫu này đều dễ khớp quá mức. Đây là giới hạn đã
  biết của mọi cổng theo xu hướng, không phải lỗi cần sửa ngay.

---

## 6. Tổng hợp: học được gì, và giới hạn của phép đo

### 6.1 Những điều học được

1. **Độ rộng mang thông tin mà MA200 không có.**
   - Tín hiệu phá nền lúc độ rộng đóng thất bại nhiều ở 2021–2026: trung vị khoảng −5%, chỉ khoảng 1/3 có lãi.
   - Độ rộng nhận ra đúng các giai đoạn chỉ số tăng nhờ vài mã trụ (2025–2026) và né được thua lỗ năm 2026.
2. **Như một cổng chặn cứng, độ rộng đổi lợi nhuận lấy an toàn, và tỷ lệ đổi không ổn định.**
   - Trong các sóng tăng lan rộng có nhịp điều chỉnh sâu (2017, 2021), cái giá rất đắt.
   - Khi thị trường hẹp hoặc đi ngang (2015–2019, 2022, 2026), phần thưởng lớn.
   - Luật đã chốt yêu cầu lợi ích nhất quán ở cả hai giai đoạn, và nó không nhất quán.
3. **Độ rộng nhạy với độ trễ khi thực thi.** Mua chậm một phiên làm lợi nhuận của biến thể có độ rộng ở giai
   đoạn chọn giảm từ +53.2% xuống +40.1%, trong khi MA200 gần như không đổi.
4. **Độ trễ hai ngưỡng 45/55% chưa đủ.** Độ rộng vẫn đổi trạng thái nhiều hơn MA200 (36 so với 20 lần ở giai đoạn
   chọn), vì nó dao động trong biên độ rất rộng.
5. **Máy nhiều trạng thái không được dữ liệu ủng hộ.** Ô "phân phối" yếu nhất quán. Nhưng ô "sóng hồi" và ô
   "gấu" đổi dấu giữa các giai đoạn, và ADX không giúp phân loại.
6. **Vấn đề lớn hơn nằm ở điểm vào lệnh.** Sổ lệnh có lãi trung bình mỗi lệnh âm ở 2021–2026 và thua chỉ gửi tiền.
   Cải thiện cổng thị trường chỉ là phần phụ.

### 6.2 Giới hạn của phép đo

- **Mẫu nhỏ ở giai đoạn xác nhận:** chỉ 21 tháng và 65 tín hiệu. Sai số của các số trung bình khoảng ±3 điểm.
- **Tín hiệu không độc lập:** các cú phá nền cùng thời điểm thường cùng thắng hoặc cùng thua theo thị trường, nên
  số tín hiệu "thật sự độc lập" ít hơn số đếm, và sai số thực tế lớn hơn ước lượng ở mục 4.6.
- **Giai đoạn lùi chỉ để đối chiếu:** rổ 2015–2020 nhỏ (62–118 mã), và sổ lệnh chỉ chấm được cơ bản từ 2018-02-15.
- **Tầng tín hiệu chưa thực tế hoàn toàn:** lợi nhuận chưa trừ phí và chưa qua các cổng cơ bản, tin tức, dòng
  tiền ngoại.
- **Mức sụt sâu nhất rất nhiễu:** do một đợt sụt duy nhất quyết định (mục 5.4).
- **Sàn của mã lấy theo bảng niêm yết hiện tại** (mục 5.2).
- **Giai đoạn xác nhận đã bị xem.** Nó không còn là dữ liệu sạch cho bất kỳ biến thể mới nào.

---

## 7. Khuyến nghị

### 7.1 Việc làm ngay

- **Giữ `BREADTH_GATE_ENFORCED = False`.** Không đổi MA50, mốc 45/55/50%, hay luật qua cửa.
- **Giữ regime chính thức:** VN-Index trên MA200, cổng vĩ mô và cổng tiền tệ.
- **Dùng độ rộng như thông tin.** Phiên hằng ngày đã tính và lưu độ rộng:
  - chuỗi `BREADTH50` (tỷ lệ) và `BREADTH50_STATE` (1 là mở, 0 là đóng) trong `market_points`;
  - khối "Độ rộng" trên trang `/market`, có 20 phiên gần nhất;
  - dòng "Độ rộng" trong nhóm "Thị trường" của mỗi verdict.

  Tại phiên 2026-10-09, độ rộng là 31.2%, tức cổng đóng.
- **Nếu muốn thận trọng hơn khi độ rộng đóng** (ví dụ chọn lọc lệnh kỹ hơn, hoặc giảm số lệnh mở cùng lúc), đó
  là quyết định tùy nghi của anh. Nên ghi lại trong phần quyết định (`decisions`) để sau này đo được, chứ không
  phải luật của hệ thống.

### 7.2 Luật đo lại bằng dữ liệu chạy thật (đã duyệt ngày 2026-10-12)

Từ 2026-10-12, mỗi phiên chạy thật là dữ liệu chưa ai xem. Luật đã duyệt dưới đây là một phép đo riêng, khác
phép đo bộ lọc tín hiệu ở `docs/breadth-signal-filter.md`: hai phép dùng cùng các phiên chạy thật nhưng trả lời
hai câu hỏi khác nhau, mỗi phép có luật riêng, và không phép nào là lần thử lại của phép kia.

| Mục | Đề xuất |
|---|---|
| Dữ liệu | Chỉ các phiên từ 2026-10-12 trở đi, với độ rộng do phiên chạy thật lưu |
| Thời điểm đo | Khi mỗi phía (độ rộng mở và đóng) có ít nhất 30 tín hiệu phá nền đã đủ 40 phiên, và không sớm hơn 12 tháng |
| Luật | Giữ nguyên luật hiện tại: hai tầng, ngưỡng 20%, 1 điểm, 2 điểm, 30 tín hiệu mỗi phía |
| Nếu qua | Bật `BREADTH_GATE_ENFORCED`, đồng thời cho trang `/backtest` tự áp cổng độ rộng (hiện chưa làm) |
| Nếu không qua | Giữ độ rộng ở vai trò quan sát; không thử lại cùng luật trên cùng dữ liệu |

**Ước lượng thời gian:** khoảng 35–40 tín hiệu mỗi năm, nhưng phía hiếm hơn chỉ khoảng một nửa. Năm 2026 độ rộng
chỉ mở 9% số phiên, nên hiện phía mở là phía hiếm. Vì vậy cần khoảng 1.5–2 năm.

### 7.3 Những việc không nên làm

- **Không hạ ngưỡng** 20% xuống 17%, hay tăng trần 1 điểm lên 5 điểm, vì số đã sát.
- **Không chuyển sang biến thể "chỉ dùng độ rộng"** vì thấy nó đẹp ở giai đoạn lùi và xác nhận. Đó là chọn sau khi
  đã xem số, và nó kém nhất ở giai đoạn chọn (+6.7%/năm, sụt −24.3%).
- **Không dựng máy 4–5 trạng thái,** không dùng ADX làm cổng, không thêm luật "mua tỷ trọng nhỏ trong sóng hồi"
  hay "bắt đáy hoảng loạn" (mục 5.6 và 5.8).
- **Không chạy lại báo cáo với ngưỡng khác** rồi chọn ngưỡng đẹp nhất. Mỗi lần như vậy là một lần nhìn trộm dữ liệu.

### 7.4 Ba giả thuyết cho phép thử sau

Mỗi giả thuyết dưới đây là một luật mới. Nó phải được chốt trước, và chỉ được đo trên dữ liệu chạy thật về sau.

1. **Độ rộng như bộ lọc tín hiệu, không phải cổng thị trường.**
   - *Luật:* khi MA200 mở mà độ rộng đóng, bỏ tín hiệu phá nền; danh mục và các lệnh khác không bị ảnh hưởng.
   - *Cơ sở:* đây là quy luật nhất quán nhất ở cả ba giai đoạn, với cách biệt 4.9–8.2 điểm (mục 5.5).
   - *Ưu điểm:* ít tốn lợi nhuận hơn cổng cứng, vì chỉ bỏ những tín hiệu xấu chứ không đóng cả danh mục.
   - *Đã chốt trước* ngày 2026-10-12 ở `docs/breadth-signal-filter.md` (tag `prereg/breadth-filter`), đo trên
     phiên chạy thật từ 2026-10-13, lợi nhuận tính từ giá đóng cửa phiên sau phiên tín hiệu.
2. **Độ rộng như tín hiệu quản lý lệnh đang giữ.**
   - *Luật:* khi độ rộng chuyển sang đóng, siết dừng lỗ của các lệnh đang giữ, ví dụ kéo theo MA20 sớm hơn, thay
     vì chặn mua.
   - *Cơ sở:* ô "phân phối" yếu nhất quán (mục 5.6).
3. **Làm độ rộng ổn định hơn.**
   - *Luật:* vùng đệm rộng hơn (ví dụ 40/60%), hoặc yêu cầu độ rộng vượt mốc đủ N phiên liên tiếp mới đổi trạng thái.
   - *Cơ sở:* độ rộng đổi trạng thái quá nhiều và nhạy với độ trễ thực thi (mục 5.3 và 5.4).
   - *Thận trọng:* mỗi tham số thêm vào là một bậc tự do, nên chỉ chọn *một* phương án và chốt trước.

### 7.5 Ưu tiên lớn hơn

- **Điểm vào lệnh và luật thoát lệnh.** Sổ lệnh có lãi trung bình mỗi lệnh âm ở 2021–2026 và thua chỉ gửi tiền.
  Cải thiện chất lượng tín hiệu (ví dụ điều kiện nền, xác nhận khối lượng) và luật thoát lệnh có tác động lớn hơn
  bất kỳ cổng thị trường nào.
- **Dữ liệu và công cụ:**
  - lưu lịch sử sàn của từng mã, để biên độ khi phát hiện bước gãy đúng theo thời điểm;
  - rút ngắn thời gian chạy sổ lệnh, hiện khoảng 22 phút cho hai sổ;
  - thêm vào báo cáo một mục đo trên dữ liệu chạy thật, để luật đo lại ở mục 7.2 chạy được bằng một lệnh.

---

## 8. Chạy lại và file liên quan

**Chạy lại báo cáo:**

```bash
cd research && PYTHONPATH=. python3 -m app.breadth_report
```

- Mất khoảng 22 phút: độ rộng 5 giây, quét tín hiệu khoảng 15 giây, phần còn lại là hai sổ lệnh chạy song song.
- Cần bảng sàn ở `backend/data/vstock.db` (hoặc đường dẫn trong `VSTOCK_MARKET_DB`). Thiếu bảng thì lệnh dừng.
- Kết quả ghi đè `research/reports/breadth_gate.md`.

**File liên quan:**

| File | Nội dung |
|---|---|
| `research/app/config.py` | Các hằng số `BREADTH_*`: MA50, mốc 55/45/50%, 30 mã, 5 phiên, luật qua cửa, cờ `BREADTH_GATE_ENFORCED`, tên chuỗi `BREADTH50` |
| `research/app/breadth.py` | Tính độ rộng, phát hiện bước gãy, trạng thái có độ trễ hai ngưỡng, câu mô tả trạng thái |
| `research/app/breadth_report.py` | Ba tầng đo, bảng bốn ô, độ trễ sau đáy, và kết luận qua cửa |
| `research/tests/test_breadth.py` | Test cho phép đếm, nến cũ, bước gãy, đổi rổ đầu năm, độ trễ hai ngưỡng, trang `/market`, và việc khóa khi bật cờ |
| `research/app/backtest.py` | Tham số `breadth_open` của `run_backtest` |
| `research/app/evaluate.py` | `compose` nhận trạng thái độ rộng; chỉ khóa khi `BREADTH_GATE_ENFORCED` bật |
| `research/app/pipeline.py` | Hàm `_breadth`: nạp nến cho mã của rổ ngoài danh sách theo dõi, tính và lưu độ rộng mỗi phiên |
| `research/app/web.py`, `research/templates/market.html` | Khối "Độ rộng" trên trang `/market` |
| `research/reports/breadth_gate.md` | Báo cáo sinh tự động |
| `research/reports/breadth_gate_explained.md` | Bản giải thích này |

**Số không có trong `breadth_gate.md`:** bảng phân rã theo năm (mục 5.4), độ lệch chuẩn và sai số của lợi nhuận 40
phiên (mục 4.6), và ví dụ phiên 2026-10-09 (mục 4.3). Các số này được tính riêng bằng cùng các hàm của báo cáo
(`breadth_by_day`, `breadth_states`, `find_signals`, `_rotation`, `_segment`).
