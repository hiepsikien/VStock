# Dynamic cho Flute và Piano của Giao hưởng

Kế hoạch cho hai bè đang đứng một mức suốt bài. Flute in một chữ `mp` ở ô 1, velocity cố định `FLUTE_VELOCITY = 64`, không hairpin. Piano in một chữ `p` ở ô 1; hợp âm đệm không gắn velocity, fill cuối câu đứng ở `FILL_VELOCITY = 64`. Violin, Cello và Bass đã có đường dynamic. Tài liệu này đưa Flute và Piano vào cùng khuôn đó.

Chỉ Giao hưởng. Jazz, Tối giản và Ambient giữ cách viết hiện tại. Piccolo, Glockenspiel, Harp và sáu kèn cor đứng cùng vai P5 và P3, nên chúng nhận cùng đường dynamic khi bộ nhạc cụ đổi.

## Flute thở theo câu nó hát

Flute vào khi câu lên cao, khi có breakout, hoặc khi nốt vượt trần violin. `_flute_and_violin_dovetail` ghi `yield_spans`, violin nhường đoạn đó, và hairpin của câu mất theo vì `melody_parts` chỉ dựng vòng cung trên đoạn violin còn giữ. Flute nhận lại vòng cung của đúng đoạn nó hát.

`hairpins()` đã có: crescendo tới đỉnh, diminuendo ra, mỗi cạnh dài ít nhất `WEDGE_MIN` (2 móc đơn). Flute dùng hàm đó trên từng đoạn của chính nó. Đỉnh là nốt cao nhất của đoạn flute, không phải đỉnh câu nếu đỉnh câu nằm ở violin.

Đoạn được vòng cung khi câu lên ít nhất `MIN_RISE` (3 nửa cung) và đoạn flute dài từ 2 móc đơn. Đoạn phẳng, hoặc đoạn một móc, giữ một mức.

Sàn là `mp` (velocity 64). Trần là `mf` (velocity 80). Nốt nhấn trong đoạn chạm trần. Vùng Sol5–Mi6 đứng ở `mf` vẫn còn hơi; `f` (96) làm sáo gắt. Đường velocity là `swell()` của câu, kẹp trong khoảng này, rồi ghi thành thuộc tính `dynamics` trên từng nốt để MuseScore phát đúng chữ in.

Chữ trên khuông:

- `mp` ở tiếng vào của đoạn.
- `mf` ở đỉnh khi vòng cung thực sự nở.
- `mp` in lại ở tiếng đánh mới sau diminuendo.

Hairpin không có chữ đích đẩy playback lên một bậc rồi đứng ở đó. Violin đã xử lý bằng `drift` trong `melody_parts`: in lại `mp` ở nốt đánh mới đầu tiên, không trên nốt nối dây. Flute dùng cùng luật.

Warm-up và cool-down vẫn để sáo nghỉ, như `movement_frame` đang cắt `score.high` về thân. Hairpin và chữ của sáo chỉ nằm trong thân. Không thêm `p` đầu khung hay `ppp` cuối khung cho bè này.

## Piano nở theo thanh khoản

Hợp âm đệm không đi theo hairpin giai điệu. P3 mang `<harmony>`, và MuseScore phát ký hiệu hợp âm ở mức dynamic của P3. Piano phồng theo câu violin thì lớp hợp âm phồng theo.

Giường piano dùng cùng cửa sổ thanh khoản với bass (`liquidity_windows_for`, hoặc `LIQUIDITY_WINDOWS` ở bản ngày). Chữ là một bậc dưới band thô, trần `mp`:

| Band thô | Piano |
|---|---|
| `p` | `p` |
| `mp` | `p` |
| `mf` | `mp` |
| `f` | `mp` |

`bass_marking()` để `mp` khi band là `mp`. Piano không gọi hàm đó. Một hàm anh em, chẳng hạn `piano_marking()`, hạ một bậc rồi kẹp ở `mp`.

Chữ đổi ở phách 1 của cửa sổ, và chỉ in khi khác chữ đang đứng. Cùng cách `_bass_part` bỏ chữ lặp. Guide tone và tay trái gắn velocity của chữ đó: 49 cho `p`, 64 cho `mp`.

Fill cuối câu nói hơn giường một bậc, trần `mf`:

| Giường | Fill |
|---|---|
| `p` | `mp` (64) |
| `mp` | `mf` (80) |

Chữ lớn hơn được in ngay tiếng fill. Chữ của giường được in lại ở hợp âm đệm kế tiếp, để playback không kẹt ở `mf`. Fill dài 2–6 móc đơn, nên không thêm hairpin trên piano.

Khung tĩnh: piano nghỉ ở warm-up và cool-down (`_rest_comp`). Những ô đó không có chữ mới. Khung động: piano đánh ở warm-up và `tag_bars` đầu cool-down; những ô đó giữ `p`. Phần cool-down còn lại piano nghỉ. `ppp` cuối khung vẫn thuộc bass và dây.

## Chỗ để trên Score

`Score` thêm ba tuple, mặc định rỗng để Jazz, Tối giản, Ambient và mọi `Score(...)` cũ không đổi:

- `high_wedges`
- `high_dynamics`
- `comp_dynamics`

Không thêm `comp_wedges`. Piano không có hairpin.

`slice_score` dịch ô của ba tuple này cùng `lead_wedges`, `support_dynamics` và `dynamics`.

## Xuất MusicXML

`_melody_part` đã nhận wedges và dynamics. `score_to_musicxml` đưa `high_wedges` và `high_dynamics` vào P5 khi variant là `symphony`. Chữ mở đầu vẫn là `mp` nếu bè có nốt trong ô 1. Bè nghỉ hết ô 1 thì chữ đầu tiên đứng trên tiếng flute đầu tiên. Bè không hát nốt nào thì giữ một chữ `mp` ở ô 1, như hiện tại.

`_piano_part` in `comp_dynamics` khi variant là `symphony`, trước nốt của ô, một lần cho cả hai khuông. Nhánh `variant == "jazz"` và `low_wedges` giữ nguyên. Tối giản và Ambient không đi qua nhánh chữ mới: Tối giản vẫn một chữ `p`, Ambient vẫn `_ambient_swell_part`.

## Khung ngày và khung chương

`apply_daily_frame` và `apply_span_frame` cắt `high_wedges` cùng `high_dynamics` bằng `_body_wedges` và lọc chữ vào `[body, cool)`, cùng cách đang cắt nốt flute. Không gọi `_letters` cho sáo, vì hàm đó thêm `p` lúc vào và `ppp` lúc nghỉ.

`comp_dynamics` bị cắt khỏi ô piano nghỉ. Khung động giữ chữ `p` trên warm-up và trên `tag_bars`. Thân giữ chữ thanh khoản. Không gắn `ppp` vào piano.

## Việc không làm

- Không đổi hairpin hay chữ của Violin, Cello, Bass.
- Không đổi Vibraphone, Rhodes, Synth Pulse, French Horn.
- Không cho piano hairpin theo câu giai điệu.
- Không nâng flute lên `f`.
- Không thêm `pp` vào `MARKINGS`.

## Khi đưa vào code

1. `model.py`: ba field mới trên `Score`.
2. `dynamics.py`: `piano_marking()`.
3. `_flute_and_violin_dovetail` trả thêm wedges và chữ. Velocity flute đi theo `swell()`, kẹp 64–80, và in lại `mp` theo `drift`.
4. Nhánh symphony trong `render`: gán `comp_dynamics` theo cửa sổ; guide tone và tay trái nhận velocity của giường; fill nhận bậc ở bảng trên.
5. `musicxml.py`: P5 nhận hai tuple của flute; P3 symphony in `comp_dynamics`.
6. `span.slice_score`, `movement_frame.apply_span_frame`, `daily_frame.apply_daily_frame`: cắt và dịch ba tuple.

## Kiểm tra

- Flute chỉ có `<wedge>` trên đoạn nó hát. Chữ chỉ `mp` và `mf`. Mọi nốt flute có velocity từ 64 đến 80.
- Đoạn flute phẳng, hoặc ngắn hơn 2 móc, không có hairpin.
- Piano chỉ có `p` và `mp` trên giường. Fill lên tối đa `mf`, rồi hợp âm đệm sau đó in lại chữ giường.
- Ô flute hoặc piano nghỉ không mang hairpin hay chữ mới. Warm-up và cool-down tĩnh không có chữ piano. Sáo không có `p` đầu khung và không có `ppp`.
- Jazz, Tối giản, Ambient giữ nguyên số chữ và số hairpin trên cả năm bè.
- Assertion hiện khóa piano Giao hưởng đúng một thẻ `<dynamics>p</dynamics>` được viết lại theo bảng band ở trên.
