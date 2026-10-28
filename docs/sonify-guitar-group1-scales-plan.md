# Scale thật trên pattern đang bị cấm

> Tham chiếu: [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md), [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md)
> Phạm vi: Villa-Lobos (`etude1`, `etude11`, `thumb_cantabile`) và Barrios (`preludio` khi `_catedral_preludio` đúng). `tremolo` giữ cửa cấm.

## Việc cần nghe được

Đoạn scale là dấu hiệu của một nhịp giá chạy lên hoặc chạy xuống. Người nghe nhận ra nó vì bè Cao rời pattern đang hát và chạy một câu liền bậc, một chiều, có hairpin cùng hướng với xung. Câu đó dùng đúng bước của tác giả. Pattern không bị đổi nốt bên trong lưới.

Bản nháp trước gắn scale vào móc đệm của Étude, vào canto của Preludio, và vào đường ngón cái. Lưới còn nguyên nên câu chạy lẫn vào figuration. Đợt này bỏ cách đó. Đoạn scale là `ScalePassage` như các pattern Nhóm 3: `_line` vẽ đường, `_install_lead` đặt bè Cao, hairpin in lại sau sóng volume.

## Vì sao Villa-Lobos và Barrios đang im

Cửa `_touches_excluded` xóa cả passage khi `[start, target]` chạm một ô `tremolo`, `etude1`, `etude11`, `thumb_cantabile`, hoặc preludio có khung. Trên MWG ngày 28/10/2026, phiên selloff có 17 xung. Sor hát `elegiaque` và nhận 9 đoạn. Villa khóa `thumb_cantabile` và nhận 0. Barrios khóa `tremolo` và nhận 0. Chương IV của tháng: Villa là `etude1` suốt 84 ô, Barrios là `tremolo` cộng preludio, cả hai nhận 0 trong khi Sor nhận 28 đoạn.

## `tremolo` đứng ngoài

Tremolo đã là câu chạy của Barrios. Mỗi phách lặp một cao độ giá qua `p–a–m–i`. Giá đổi thì cao độ cụm đổi. Thêm một đoạn scale thứ hai lên lưỡi đó vừa đứt vòng ngón, vừa che dấu hiệu sẵn có. `tremolo` ở lại trong `_GROUP1`. Ô phẳng `f` và `volatile` vẫn chỉ nhận `perpetual` như hiện tại.

Một xung nằm trọn trên tremolo không sinh passage. Một xung chỉ chạm tremolo ở đầu hoặc ở cuối thì được cắt đến biên ô tremolo. Phần còn lại, nếu còn ít nhất một ô trọn trên pattern chủ, vẫn là một đoạn scale. Tremolo nằm giữa khoảng xung thì cả passage bị bỏ: một lỗ ở giữa làm đứt câu chạy.

## Pattern nào nhường chỗ

`etude1`, `etude11`, `thumb_cantabile`, và preludio có khung nhận scale thật. Trong các ô passage chiếm, bè Cao và bè Trung của pattern im. Bè Cao là câu scale. Bè Trầm của pattern còn lại, để ô vẫn thuộc bài của tác giả.

Passage trên các pattern này ăn trọn ô. Biên xung được kéo vào trong tới đầu ô và cuối ô. Phần còn lại ngắn hơn một ô thì không có passage. Xung ngắn hơn một ô giữ nguyên pattern. Không khoét nửa vòng 16 móc kép, nửa chùm sextuplet, hay nửa khung canto.

Vùng pattern liên tiếp để một ô đầu vang đúng lưới, rồi passage mới được mở. Đáp xuống `target` thì lưới pattern trở lại ngay ở ô sau. Cùng ý với «thiết lập pattern trước» của Nhóm 2, áp vào bốn pattern này.

Ô pedal vẫn loại. Ngân sách 30% và khoảng thở một ô giữ nguyên. Các ô này không cộng `base_intrinsic_eighths`.

## Câu scale nghe ra tác giả

Hạt nốt, retreat, nốt đích, và cửa sổ lực lấy từ kế hoạch scale hiện có. Dưới 88 BPM đi móc đơn. Từ 88 đi móc kép, kể cả Barrios ở 120. Nốt đích là `ctx.melody` tại eighth đầu của ô sau passage, để pattern vào lại đúng giá.

Hairpin một chiều trên bè Cao là dấu lên hoặc xuống. Sóng lên mở `soft` và chạm `loud` tại đích. Sóng xuống mở `loud` và về `soft` tại đích. Hai étude dùng cửa sổ Động năng. Thumb cantabile và Preludio Saudade dùng cửa sổ Hát. Bass và bè giữa không đi hairpin này.

**Villa-Lobos.** Bước là `villa_scale_step`: diatonic cộng màu `sus2`, `add9`, `7sus4`. Dây buông chỉ vào câu khi chùm bốn móc kép vẫn qua `_quarter_ok` và `_position_ok`. Đây là đường *Étude No. 7*, tay phải chạy scale, không phải vòng *Étude No. 1*.

- `etude1`: bass gốc gảy một lần và ngân hết ô, đúng ô étude. Vòng 16 móc kép và hai nốt hát nghỉ suốt các ô passage.
- `etude11`: bass gốc vẫn vào mỗi phách, nên mạch Animé còn dưới câu chạy. Bốn chùm sextuplet nghỉ.
- `thumb_cantabile`: một nốt gốc ngân ở vùng cello, bè Trầm. Câu hát ngón cái và hai nốt chập phách yếu nghỉ. Câu scale hát ở bè Cao, trên nốt gốc đó, và phải `_playable` với nó.

**Barrios.** Bước là `barrios_scale_step`. Nốt dẫn nửa cung chỉ ngay trước phách mạnh hoặc trước nốt đích, đúng `barrios_chromatic_approach`.

- Preludio có khung: bass hai ô của *La Catedral* giữ nếu còn chơi được với câu scale. Không chơi được thì ô đó lấy gốc trên phách mạnh, cùng luật bass của passage Barrios hiện có. Canto, sóng chữ V, và chuông nghỉ suốt các ô passage.
- Preludio không khung giữ overlay Nhóm 3 như cũ, kể cả đoạn ngắn hơn một ô.

## Passage đi qua hai pattern

Một câu scale là một đường liền bậc duy nhất. Ô Nhóm 3 trong cùng passage vẫn overlay như hiện tại, kể cả khi đoạn đó ngắn hơn một ô ở phía Nhóm 3. Ô thuộc bốn pattern chủ thì trọn ô là scale, bass riêng của ô đó. Ô tremolo không nằm trong passage. Bước liền bậc tính trên các nốt scale thực sự kêu.

Khoảng thở một ô đo từ `target` của passage sau khi đã cắt biên.

## Sửa trong code

`guitar_scale_passages.py`

- `_GROUP1` chỉ còn `tremolo`.
- Passage chạm `etude1`, `etude11`, `thumb_cantabile`, hoặc preludio có khung thì được phép. Cắt `[start, target]` vào các ô trọn thuộc pattern chủ. Bỏ ô tremolo ở hai đầu. Tremolo hoặc pedal nằm giữa thì hủy passage. Phần còn lại ngắn hơn một ô trên pattern chủ thì hủy.
- Ô đầu của một vùng pattern chủ liên tiếp không được là ô mở của passage.
- Hiện thực hóa bằng `_line` và `_install_lead`. Xóa lead và support của pattern trên các ô đã nhường. Giữ bass theo mục «Câu scale nghe ra tác giả».
- Hairpin và cờ `hairpin` đi cùng đường in lại sau `apply_guitar_wave`.

`guitar.py`, `guitar_villa.py`, `guitar_barrios.py`

- Không thêm đường đổi cao độ bên trong vòng étude, sextuplet, canto, hay ngón cái.
- Mỗi pattern chủ có một bass cho ô đang bị scale chiếm: một nốt ngân cả ô (`etude1`, thumb), bass từng phách (`etude11`), bass hai ô hoặc gốc phách mạnh (preludio có khung).

`guitar_patterns.py`

- Các ô đã nhường không đi extra của `_shape_dynamics`. Lực câu scale đến từ hairpin in lại.
- Pickup và caesura tiếp tục nhường eighth thuộc `scale_eighths`.

## Kiểm tra

Sửa các test đang đòi passage rỗng khi chạm `etude1`, `etude11`, `thumb_cantabile`, hoặc preludio có khung. Test tremolo vẫn đòi passage rỗng khi xung nằm trọn trên tremolo.

Thêm:

- Trên một ô étude, thumb, hoặc preludio có khung đã nhường: bè Cao là các bước cách nhau tối đa 2 bán cung, đúng hướng xung, đích trùng `melody`. Không còn vòng 16 móc kép, sextuplet, canto, sóng chữ V, hay hai nốt chập.
- Bass của ô đó còn đúng hợp đồng của pattern. `assert_playable` với profile Villa hoặc Barrios, gồm `_quarter_ok` khi có dây buông.
- Xung ngắn hơn một ô trên các pattern này không sinh passage. Ô đầu của vùng pattern vẫn là lưới pattern.
- Xung chạm tremolo ở cuối bị cắt. Xung có tremolo ở giữa bị hủy. Xung chỉ toàn tremolo không có passage.
- Hairpin bè Cao đi một chiều. Nốt scale còn đúng velocity sau `humanize` với offset `+2`.
- Tổng eighth scale của thân bài vẫn trong 30%, trừ scale nội tại Nhóm 2.

## Ngoài đợt này

Bộ chọn pattern theo mood giữ nguyên. Trần 30%, dò xung trên giá đóng, khoảng thở một ô, và hạt nốt theo `SCALE_SIXTEENTH_MIN_BPM` giữ nguyên. Nhóm 2 giữ cửa sổ nửa ô và cầu nối dài. Bach và Brouwer không đổi.
