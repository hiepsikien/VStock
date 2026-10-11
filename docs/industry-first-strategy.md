# Strategy ngành, mã, rồi thời điểm

Một đợt tăng hoặc một đợt giảm thường đi cả ngành. Từng mã trong ngành chỉ khác nhau ở mức tăng nhiều hay tăng ít. Vì vậy quyết định đi từ trên xuống: vĩ mô mở ngành nào, trong ngành đó mã nào đáng giữ, rồi mới chọn phiên vào, quy mô và cách thoát.

Điểm nền giá và cơ bản hiện tại trong [`research/app/evaluate.py`](../research/app/evaluate.py) là tầng cuối. Nó chưa được phép một mình quyết định `Được vào`.

```mermaid
flowchart TD
  macro[ViMoToanCauVaNoiDia]
  industry[NganhMo]
  stock[MaTrongNganhMo]
  timing[NenGiaChonPhien]
  book[SizeVaThoat]
  macro --> industry
  industry --> stock
  stock --> timing
  timing --> book
```

## Methodology

Mỗi tầng chỉ trả lời một câu. Tầng dưới không được sửa câu trả lời của tầng trên.

- Vĩ mô trả lời: môi trường này có đang cho phép một nhóm ngành tăng hay không. Cùng một số cho mọi mã trong ngày. Nó không chọn mã.
- Ngành trả lời: ngành nào đang trong sóng, so với VN-Index và so với chuỗi dẫn đã ấn định. Nó không chọn mã trong ngành, và không chọn phiên mua.
- Mã trả lời: trong ngành đang mở, tên nào có vị thế bền và giá còn rẻ so với chính nó và so với ngành. Danh sách này đổi chậm, theo quý và theo vốn hóa, không theo từng phiên.
- Thời điểm trả lời: trong danh sách đã khoanh, phiên nào nền giá cho phép mua. Nền giá không được kéo một mã ở ngành đang đóng vào sổ.
- Sổ trả lời: mua bao nhiêu và giữ bao lâu. Mục tiêu là đi theo sóng ngành, thường trong khoảng 3–12 tháng, trần 132 phiên. Vào vì ngành thì ra vì ngành. Phí cả vòng 0,3% nhỏ so với một đợt tăng 20% nếu giữ được nửa năm.
- Rổ là VN100, 100 mã lớn và thanh khoản nhất trên HOSE, thay cho 51 mã đang viết trong `DEFAULT_UNIVERSE`. Danh sách dựng lại vào ngày 1 tháng 1 mỗi năm theo vốn hóa lúc đó. Mã rời rổ năm sau vẫn ở trong năm đã chọn, để kết quả không chỉ toàn những mã còn sống đến hôm nay.

Ba định nghĩa khóa trước khi đo, không chỉnh sau khi đã thấy kết quả:

- Một đợt tăng của một mã là cửa sổ 66 phiên liên tiếp, giá cuối cao hơn giá đầu ít nhất 20%, các cửa sổ của cùng một mã không chồng nhau. Giữ cách chọn tham lam theo mức tăng đã dùng khi đếm 123 đợt.
- Cửa sớm của đợt đó là các phiên từ ngày đầu cửa sổ cho đến trước phiên giá đóng cửa đã cao hơn giá đầu quá 15%. Muốn bắt đợt tăng thì tín hiệu phải rơi vào cửa này.
- Một ngành đang mở là một trạng thái theo ngày, tính từ lợi suất 60 phiên. Ngành đóng khi lợi suất đó không còn cao hơn VN-Index, hoặc chuỗi dẫn bắt buộc đang giảm. Chi tiết ở mục xác định ngành.

Luật cứng đã có vẫn đứng trước mọi tầng: giá chưa chỉnh chia tách, đình chỉ hoặc ngoại trừ kiểm toán, VN-Index dưới MA200, và đăng ký bán của người nội bộ. Chúng không bị điểm hay ngành ghi đè. Việc đóng cửa dưới đỉnh nền thuộc tầng thoát, nói ở mục sau.

## Cách validate

Có hai phép đo, vì hai câu hỏi có hai cỡ mẫu khác nhau. Trộn chúng sẽ bảo một tầng đúng trong khi sổ lệnh lỗ, hoặc bác một tầng đúng chỉ vì vài lệnh.

Phép đo tầng ngành và tầng mã đếm từng phiên. Chọn quy tắc trên các đợt bắt đầu từ 2021-01-01 đến 2024-12-31. Chỉ kết luận khi cùng quy tắc đó còn đúng với các đợt bắt đầu từ 2025-01-01 đến 2026-10-09. Không được nới ngưỡng sau khi xem giai đoạn xác nhận. Giai đoạn 2021–2024 có cả sóng tăng 2021 và sóng giảm 2022. Nến và chuỗi vĩ mô được kéo từ `HISTORY_START = "2021-01-01"` trong [`research/app/ingest.py`](../research/app/ingest.py) để kho bắt đầu từ 2021. Báo cáo quý trong kho đã có từ 2017.

Phép đo sổ lệnh đếm lệnh đã đóng, theo giá thoát thật, không theo nhãn 66 phiên. Trên cửa sổ 2024-04 đến 2026-10, khoảng 620 phiên, nếu năm suất luôn đầy và mỗi lệnh giữ hết 132 phiên thì cả sổ chỉ có khoảng 23 lệnh. Năm 2026 dài khoảng 185 phiên, một lệnh 132 phiên chỉ kịp một vòng, cả sổ khoảng 5 đến 8 lệnh. Cỡ đó không đủ để kết luận có lợi thế. Một mã tăng 60% hoặc một mã gãy cũng quyết định cả năm. Vì vậy sổ lệnh không được chấm đậu hay trượt trên riêng năm 2026. Nó được chấm trên toàn bộ 2021–2026, và phải có ít nhất 30 lệnh đã đóng thì các tỷ lệ mới được đem ra kết luận. Chưa đủ 30 lệnh thì chỉ công bố số lệnh, lợi nhuận và sụt sâu nhất, chưa đổi `Được vào`.

Với một quy tắc “mở” (ngành mở, hoặc mã được khoanh):

- Recall: số đợt tăng có ít nhất một phiên cửa sớm mà quy tắc đang mở, chia cho số đợt tăng.
- Precision: số phiên quy tắc mở mà 66 phiên sau đó tăng ít nhất 20%, chia cho số phiên quy tắc mở và còn đủ 66 phiên phía trước. Với cổng ngành, đơn vị là ngành-phiên. Với cổng mã, đơn vị là mã-phiên.
- Tỷ lệ nền: precision của quy tắc “luôn mở”. Quy tắc mới chỉ có ích khi precision của nó cao hơn tỷ lệ nền.
- Ngưỡng qua cửa, ấn định trước. Recall ít nhất 60% trên giai đoạn chọn và trên giai đoạn xác nhận. Precision ít nhất gấp đôi tỷ lệ nền trên cả hai giai đoạn. Thiếu một vế thì tầng đó chỉ được ghi vào verdict để theo dõi, chưa được chặn `Được vào`.

Lý do ngưỡng này: điểm 60 trên rổ cũ bắt được khoảng 68% đợt tăng nhưng precision chỉ khoảng 16%, gần với việc mua rất nhiều phiên. Một cổng ngành mà đóng quá tay sẽ mất đợt tăng. Một cổng mà mở gần như luôn luôn thì không hơn cái điểm hiện tại.

Nhãn 66 phiên và lệnh giữ tới 132 phiên là hai việc khác nhau. Một mã có thể đạt +25% ở phiên 50 rồi về +2% hoặc âm ở phiên 132. Phép đo tầng ngành vẫn ghi là có đợt tăng. Sổ lệnh ghi hòa hoặc lỗ. Mỗi báo cáo sổ vì vậy có thêm một dòng: với các mã đã +20% ở phiên 66, lợi nhuận trung vị ở phiên 132 và ở ngày thoát thật là bao nhiêu. Dòng này cho biết giữ hết trần có trả lại phần sóng đã bắt được hay không.

Ngoài recall và precision, ghi thêm hai số để khỏi nhầm đơn vị:

- Số ngành mở trung bình mỗi phiên. Nếu gần bằng toàn bộ ngành có đủ mã, cổng không lọc.
- Trong các ngành mở, phân phối mức tăng 66 phiên của mã hạng cao và mã hạng thấp. Bước chọn mã chỉ qua cửa khi hạng cao có trung vị cao hơn hạng thấp trên cả hai giai đoạn.

LLM được chấm riêng, không trộn vào precision của cổng số. Mỗi nhận định tháng được so với các đợt tăng bắt đầu trong ba tháng sau đó. LLM chỉ được tham gia chọn ngành khi danh sách ngành nó nêu chứa đợt tăng thường hơn việc lấy mọi ngành đang mở theo cổng số.

Kết quả mỗi lần đo ghi thành một báo cáo trong `research/`, gồm số đợt, recall, precision, tỷ lệ nền, và giai đoạn. Không chỉnh định nghĩa đợt tăng giữa các báo cáo.

## Cách xác định ngành

Bảng ngành cho rổ VN100 của từng năm, file mới [`research/app/industries.py`](../research/app/industries.py). Ngân hàng, chứng khoán, bảo hiểm xuất phát từ `BANKS`, `SECURITIES`, `INSURERS` trong [`research/app/config.py`](../research/app/config.py), rồi bổ sung mã VN100 cùng nghề. Các nghề khác map tay một lần cho cả rổ, không suy từ tên công ty lúc đo.

Nhóm đủ từ ba mã, mới được có lợi suất ngành và cổng ngành:

- Ngân hàng: 18 mã trong `BANKS`.
- Chứng khoán: 10 mã trong `SECURITIES`.
- Bảo hiểm: `BVH`, `BMI`, `BIC`, `MIG`, `PVI`.
- Bất động sản: `VIC`, `VHM`, `VRE`.
- Năng lượng: `GAS`, `PLX`, `PVS`.
- Tiêu dùng: `VNM`, `MWG`, `MSN`, `SAB`, `PNJ`.

Danh sách mã ở trên là nhân của rổ 51 mã hiện tại. Khi rổ thành VN100, vật liệu, vận tải, công nghệ và nông nghiệp có thể đủ ba mã. Nhóm nào vẫn dưới ba mã thì chỉ có nhãn, không có cổng “mạnh hơn ngành”, vì lợi suất ngành trùng với chính mã đó. Những mã đó chỉ đi tiếp khi cổng vĩ mô trong nước đang mở, rồi bị xét như từng mã.

Lợi suất ngành một phiên là trung bình cộng phần trăm thay đổi giá của các mã cùng ngành có nến phiên đó. Thiếu một mã thì trung bình trên số mã còn lại. Lợi suất 60 phiên là giá trị tích lũy của chuỗi lợi suất ngày đó. Cùng cách tính cho VN-Index trên đúng các phiên đó.

Một ngành đủ mã được gọi là mở tại một phiên khi đủ các điều sau, tính chỉ với dữ liệu đến hết phiên hôm trước, để không dùng chính phiên đang xét:

- Lợi suất ngành 60 phiên kết thúc hôm qua cao hơn lợi suất VN-Index 60 phiên.
- Nếu ngành có chuỗi dẫn: lợi suất chuỗi dẫn 60 phiên kết thúc hôm qua dương. Năng lượng dùng giá dầu `CL=F`. Các ngành còn lại trong danh sách đủ mã không có chuỗi nước ngoài. Không thử chỉ số Hàn Quốc, Trung Quốc hay Mỹ cho ngân hàng, chứng khoán, bất động sản, tiêu dùng, bảo hiểm.
- Ngành nội địa cần thêm một xác nhận trong nước. Ngân hàng và chứng khoán: trung vị tăng trưởng dư nợ năm của các ngân hàng trong rổ, quý gần nhất đã qua 45 ngày, lớn hơn 0. Bất động sản, tiêu dùng, bảo hiểm: VN-Index hôm qua còn trên MA200. MA200 là điều kiện nền đã có trong [`market_regime`](../research/app/pattern.py). Nó không thay cho việc ngành phải thắng chỉ số.

Chuỗi dẫn và điều kiện trong nước được ghi cứng trong `industries.py` trước lần đo đầu. Thêm một nước hoặc một độ trễ sau khi đã xem 123 đợt là đổi đề sau khi biết đáp án. Việc đó phải tính là một quy tắc mới và phải qua lại từ đầu trên giai đoạn 2021–2024 rồi mới được nhìn 2025–2026.

Vĩ mô toàn cầu và trong nước được lưu để cổng này đọc lại được, không chỉ để trang live:

- [`fetch_macro`](../research/app/ingest.py) đổi từ 6 tháng, chỉ giữ trong bộ nhớ, sang range dài và ghi vào `market_points`. Dầu và USD/VND lấy từ Yahoo.
- Lãi tái cấp vốn giữ bảng ghi tay trong config.
- Lãi qua đêm và lợi suất 10 năm không có lịch sử trên nguồn giá tức thời. Chưa điền số giả. Khi nào có nguồn lịch sử thì thêm như một xác nhận trong nước thứ hai, và đo lại từ đầu.
- Tín dụng là trung vị `CUSTOMER_LOANS_AQ_GRYOY` của các ngân hàng, cùng độ trễ báo cáo với điểm cơ bản.

LLM đọc cùng các số này vào ngày làm việc đầu tháng. Prompt không chứa giá các tháng sau, không chứa tên các đợt tăng, và không yêu cầu chọn mã. Đầu ra là danh sách ngành ưu tiên trong các ngành đủ mã, kèm một đoạn lý do. Lưu prompt và câu trả lời. Cổng số vẫn là cổng được phép chặn lệnh. LLM chỉ được nâng thành nguồn chọn ngành sau phép so ở mục validate.

Ví dụ cách đọc, không phải ngưỡng mới: giữa 2025, chứng khoán và bất động sản tăng cả nhóm. Cổng ngành phải mở chứng khoán vì lợi suất nhóm đó thắng VN-Index, rồi mới xét `SSI`, `VND`, `SHS`. Nó không cần `SHS` là công ty lớn nhất ngành thì ngành mới được gọi là mở.

## Cách chọn cổ phiếu trong ngành

Chỉ xét mã thuộc ngành đang mở. Ngành đóng thì mã đó không vào danh sách khoanh, dù nền giá có đẹp. Mã thuộc ngành một tên thì không dùng bước này. Nó chỉ còn cổng vĩ mô và, sau này, nền giá.

Trong ngành đang mở, mỗi mã có bốn số, tính đến hết phiên hôm trước:

- Hạng vốn hóa: vốn hóa bằng số cổ phiếu lưu hành gần nhất đã biết nhân giá đóng cửa. Hạng 1 là lớn nhất ngành.
- Hạng doanh thu: doanh thu quý gần nhất đã qua 45 ngày, với ngân hàng thì thay bằng dư nợ. Hạng 1 là lớn nhất ngành.
- Rẻ so với chính mình: P/E trượt chia cho trung vị P/E trượt của mã đó trong ba năm liền trước. P/E trượt là vốn hóa chia tổng lợi nhuận bốn quý đã công bố. Nhỏ hơn 1 là rẻ hơn quá khứ của chính nó.
- Rẻ so với ngành: P/E trượt chia cho trung vị P/E trượt của các mã cùng ngành trong ngày. Nhỏ hơn 1 là rẻ hơn ngành.

P/E âm hoặc lợi nhuận bốn quý không dương thì không có mức rẻ. Mã đó vẫn có hạng vị thế, nhưng không được điểm rẻ.

“Mạnh” ở bước này là vị thế, không phải lợi nhuận quý đang tăng. Hạng vốn hóa và hạng doanh thu là thước vị thế đo được. Bảng cân đối đã có trong điểm cơ bản, gồm nợ, dòng tiền, nợ xấu và bao phủ với ngân hàng, chỉ dùng như một cờ loại: mã đang vi phạm trần nợ, nợ xấu hoặc pha loãng có hại thì rời danh sách khoanh. Không cộng điểm vì lợi nhuận năm nay cao hơn năm trước. Đo thêm một chuỗi ứng viên là hiệu tăng trưởng lợi nhuận quý này trừ quý trước. Chỉ giữ chuỗi đó nếu trên giai đoạn chọn, trong cùng ngành mở, nhóm tăng tốc có trung vị lợi nhuận 66 phiên cao hơn nhóm không tăng tốc, và giai đoạn xác nhận còn cùng chiều.

Danh sách khoanh của một ngành mở lấy theo thứ tự:

- Bỏ mã vi phạm cờ bảng cân đối.
- Giữ nửa trên theo vị thế. Vị thế là hạng tốt hơn giữa hạng vốn hóa và hạng doanh thu, để một mã lớn về doanh thu nhưng vốn hóa chưa theo kịp không bị loại chỉ vì giá đang thấp.
- Trong nửa đó, xếp theo độ rẻ so với ngành, rồi độ rẻ so với chính mình. Thiếu P/E thì xếp sau các mã có P/E.
- Mỗi ngành mở giữ tối đa ba mã. Cả sổ vẫn tối đa năm suất trong [`MAX_SLOTS`](../research/app/config.py). Nếu nhiều ngành cùng mở, lấy mã có độ rẻ so với ngành tốt nhất cho đến khi đủ năm suất.

Phép đo của riêng bước này, chỉ trên các mã thuộc ngành mở:

- Recall mã: trong các đợt tăng của ngành đó, bao nhiêu đợt có mã nằm trong danh sách khoanh ngay tại cửa sớm.
- Tách hạng: trung vị lợi nhuận 66 phiên của các mã được khoanh trừ trung vị của các mã cùng ngành mở nhưng không được khoanh.
- Qua cửa khi recall mã ít nhất 50% trên cả hai giai đoạn, và trung vị nhóm được khoanh cao hơn nhóm bị loại trên cả hai giai đoạn. Ngưỡng 50% thấp hơn recall ngành vì trong một sóng, một phần mã tăng ít vẫn là đúng cấu trúc “tăng cả ngành, nhiều ít tùy mã”. Bước này có nhiệm vụ nghiêng về mã tăng nhiều, không có nhiệm vụ bắt mọi mã trong ngành.

`SHS` là case để soi sau khi đo, không phải để nới quy tắc. Nếu sóng chứng khoán mở mà hạng vị thế loại `SHS` và vì thế mất đợt tăng lớn, báo cáo phải ghi số đó. Nếu mất nhiều đợt tương tự đến mức không qua cửa, bước vị thế không được chặn. Khi đó danh sách khoanh trong ngành mở xếp theo độ rẻ, không cắt theo hạng.

## Rủi ro khi nắm tới 132 phiên

Hai rủi ro này được tính trên chính sổ và code hiện tại, trước khi nới trần nắm.

Cỡ mẫu của sổ lệnh thì nhỏ. Khoảng 620 phiên từ 2024-04 đến 2026-10, năm suất, mỗi lệnh giữ hết 132 phiên, thì cả sổ chỉ khoảng 23 lệnh nếu các suất luôn đầy. Giai đoạn xác nhận 2025–2026 dài hơn một mình năm 2026, nhưng một lệnh 132 phiên trong 185 phiên của năm 2026 vẫn chỉ kịp một vòng. Vài lệnh không phân biệt được lợi thế với may rủi. Một mã tăng mạnh hoặc một mã gãy quyết định cả đoạn xác nhận. Cách xử lý nằm ở phép đo sổ lệnh: kéo lịch sử về 2021, đếm lệnh đã đóng trên cả giai đoạn, và chưa kết luận khi dưới 30 lệnh. Cổng ngành thoát sớm cũng làm lệnh ngắn lại, nên số lệnh sẽ nhiều hơn trần 23. Đó là hệ quả, không phải lý do để bỏ việc kéo dữ liệu về 2021.

Sụt vốn khi thị trường chỉnh thì đến từ cách thoát, không chỉ từ độ dài nắm. Trên nhánh này, [`fell_under_base`](../research/app/exits.py) cắt mọi phiên đóng cửa dưới đỉnh nền, suốt đời lệnh, không chỉ ba phiên đầu. [`TIME_STOP_SESSIONS`](../research/app/config.py) là 30 và [`MAX_HOLD_SESSIONS`](../research/app/config.py) là 60. Sau khi chốt một phần ba tại +1R, dừng lỗ kéo theo MA20 trừ 0,5 ATR. Nếu bỏ hai đồng hồ và chỉ để trần 132 phiên, một mã đã qua ba phiên đầu sẽ ngồi đến khi chạm đáy nền hoặc đủ 132 phiên. Đáy nền thường nằm sâu. Nhịp chỉnh 15–35 phiên của VN-Index, như các đợt 2022 và 2024, đủ để kéo một lệnh đang lãi về lỗ. Năm suất có thể chiếm hết tiền mặt dù không mã nào đạt trần 35%, vì năm lần 35% là 175% và không cùng tồn tại. Hết tiền mặt thì sóng ngành mới không có suất để vào.

## Thời điểm, quy mô, thoát

Chỉ triển khai sau khi cổng ngành đã qua cửa và đang được phép chặn. Nền giá hiện tại chỉ chạy trên danh sách đã khoanh. Một mã ngành đóng không thành ứng viên trong [`_candidates`](../research/app/backtest.py).

Quy mô giữ nguyên: rủi ro 1% vốn mỗi lệnh, trần 35% một mã, tối đa năm suất.

Trần nắm đưa lên 132 phiên chỉ khi ba cửa thoát sau đã có. Thiếu một cửa thì chưa nới [`MAX_HOLD_SESSIONS`](../research/app/config.py).

- Ra vì ngành. Lợi suất ngành 60 phiên không còn cao hơn VN-Index, hoặc chuỗi dẫn 60 phiên trở thành âm, thì mọi lệnh của ngành đó thoát ở giá đóng cửa phiên hôm sau. Đây là cửa thoát chính của một lệnh đang đi theo sóng.
- Giữ trailing stop đang có. Sau khi chốt một phần ba tại +1R, dừng lỗ lên hòa vốn rồi kéo theo MA20 trừ 0,5 ATR. Không đổi hệ số 0,5 và không đổi phần chốt một phần ba. Một lệnh đã lãi không được trả về đúng đáy nền ban đầu chỉ vì trần nắm dài hơn.
- Phá nền thất bại chỉ trong ba phiên đầu. Luật đóng dưới đỉnh nền hiện cắt suốt đời lệnh. Khi trần nắm là 132 phiên, luật đó chỉ còn hiệu lực trong ba phiên đầu. Sau đó việc thoát thuộc về ngành và trailing stop. Dừng lỗ đáy nền vẫn còn cho đến khi trailing nâng nó lên.

[`TIME_STOP_SESSIONS`](../research/app/config.py) bằng 30 chỉ được bỏ sau khi cửa ra vì ngành đã chạy. Trước đó, tiền chết 30 phiên vẫn là cách không giữ một lệnh ngành đã tắt.

Sóng giảm 2022 là bài kiểm tra riêng của sổ, không thay cho ngưỡng 30 lệnh. Báo cáo phải ghi sụt sâu nhất của sổ trong 2022 và số lệnh bị cửa ngành đóng trong nhịp đó.

## Dữ liệu cần có trước lần đo đầu

- Rổ VN100, dựng lại đầu mỗi năm theo vốn hóa.
- Nến từ 2021-01-01. Dùng [`HISTORY_START`](../research/app/config.py) để kéo đủ từ 2021-01-01, rồi ghi ngày nến sớm nhất thực tế của từng mã. Mã không có nến năm đó thì vắng trong năm đó.
- Dòng ngoại: [`fetch_foreign_flow`](../research/app/ingest.py) hết phân trang VNDirect, [`replace_flow`](../research/app/db.py) đổi thành upsert. Mỗi mã phải phủ từ 2021 nếu nguồn có. Dòng ngoại chưa tham gia cổng ngành. Nó là chuỗi ứng viên của bước chọn mã, đo cùng cách với tăng tốc lợi nhuận.
- P/E và vốn hóa tính từ nến, số cổ phiếu và lợi nhuận quý đã lưu. Ghi chuỗi theo ngày. Báo cáo quý đã có từ 2017.
- Lợi suất ngành tính lúc đo, không cần bảng giá mới.
- Dầu, USD/VND và các chuỗi Yahoo khác được lưu vào `market_points`, range đủ từ 2021.

## Cách giao

Nhánh làm việc tách từ `origin/main`. Nhánh `research-failed-breakout-exit` không dùng tiếp. `compose` ở phase ngành và phase mã chỉ thêm trường trạng thái vào verdict. `Được vào` đổi lần đầu khi cổng ngành qua giai đoạn 2025–2026. Phase chọn mã đổi danh sách ứng viên lần thứ hai khi chính nó qua cửa. Phase thoát, gồm cửa ra vì ngành và trần 132 phiên, là lần đổi cuối.

Mỗi phase có test đơn vị cho công thức lợi suất, P/E, hạng và độ trễ một phiên, cộng một báo cáo recall và precision trên hai giai đoạn. Phase thoát thêm số lệnh đã đóng, lợi nhuận tại phiên 66 so với ngày thoát, và sụt sâu nhất năm 2022.
