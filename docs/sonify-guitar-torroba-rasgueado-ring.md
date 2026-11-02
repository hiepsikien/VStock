# Torroba: rasgueado to hơn, ngân dài hơn, nốt sau vào trễ (Loại 1 / Loại 2)

> **Trạng thái**: **đã vào code**, `pytest backend/tests -q` **782 passed**.
> **Đã làm**: `apply_torroba_fan_ring` (score), `_apply_fans` + `NoteEvent.pinned` (dynamic), `_fan_hold_multipliers` (humanize), floor `3/12`, lead guard, cửa sổ `assert_playable` 6 → 12, và test cho cả ba trục.
> **Lệch nhỏ so với kế hoạch**: `_apply_fans` gọi sau hai restamp (không nằm trong `apply_guitar_wave`); `humanize()` có thêm `fan_hold: bool = True` để test style cũ tách khỏi tầng cơ thể; `fan_hold` dùng `delay_seconds = D * 60 / base_bpm[first]` để zero-sum theo thời gian thật, không theo beat danh nghĩa.
> **Đọc cùng**: [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) mục 4 (định nghĩa Loại 1 / Loại 2), [`docs/sonify-guitar-torroba-note-surface.md`](./sonify-guitar-torroba-note-surface.md), [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md), [`docs/sonify-guitar-torroba-lilt-accents.md`](./sonify-guitar-torroba-lilt-accents.md), [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md), [`docs/sonify-guitar-torroba-juglar-cushion-dynamics-tempo.md`](./sonify-guitar-torroba-juglar-cushion-dynamics-tempo.md).
> **Giữ**: không thêm pattern id, không thêm ô nhạc, không đổi form, không đổi lưới nhịp `3/4` / `4/4` / `6/8`, không đổi tempo / lilt / bar lean nền của `humanize`. Chỉ sửa **độ dài** và **velocity** của đúng ba nốt quạt, cộng `_apply_fans` ở tầng wave và một tầng tempo `fan_hold` ở humanize.

**Tóm tắt**: ba trục, ba tầng.

1. **Ngân** (`apply_torroba_fan_ring`, sau `_repair`): nới duration của **cả cụm bass**, **nốt support thấp nhất**, và **lead** tới `min(nốt kế tiếp cùng bè, vạch nhịp, CAP)`. CAP: Loại 1 `1,5 / 1,0 / 0,75` phách; Loại 2 `1,0 / 0,75 / 0,5`. Mở cửa sổ `assert_playable` 6 → 12 twelfth cho bar có quạt.
2. **To** (`_apply_fans`, sau `apply_guitar_wave` + hai restamp, **trước** humanize): nâng lead lên `peak + 3` (Loại 1) / `peak + 2` (Loại 2) nếu còn ở dải ấm; nếu vượt `64` thì cả cụm vào dải móng `73 / 71 / 69`. Humanize **không** quyết định độ to; nốt quạt được `pinned` nên humanize bỏ qua.
3. **Nhịp** (`_fan_hold_deltas`, trong tempo clock Torroba): nốt **ngay sau** cú quạt vào trễ `1/12` phách (Loại 1) / `1/24` phách (Loại 2), rồi bù lại trong ô. Không đổi `NoteEvent.beat`, chỉ đổi `TempoEvent`.

---

## 0. Yêu cầu đã chốt

Một cú rasgueado của Torroba, **dù là loại nào**, phải có ba đặc trưng:

1. **To hơn nền xung quanh một chút.** Cú quạt phải nổi lên so với các nốt arpeggio / chord melody đang chạy trong cùng ô, không được lẫn vào.
2. **Ngân dài hơn giá trị đang ghi trên bản nhạc một chút.** Sau khi quạt xong, âm phải còn vang thêm, không tắt đúng lúc hết giá trị nốt.
3. **Nốt ngay sau cú quạt vào trễ hơn một chút.** Tay trái chuyển thế bấm / nhả hợp âm nên nốt kế không rơi đúng phách; nghệ sĩ mượn một khoảng rất ngắn rồi bù lại ngay sau đó.

Hai loại chỉ khác nhau **mức độ**, không khác **tính chất**:

| Loại | Vai trò | Code hiện tại |
|---|---|---|
| **Loại 1** | Attack / báo hiệu mở câu | `max_notes=6`, `accent=True`, `bed_steps=0` |
| **Loại 2** | Làm mềm chord melody | `max_notes=4`, `accent=False`, `bed_steps=1` |

Ưu tiên vi mô khi cả ba bè còn chỗ: **lead ngân dài nhất → bass → support ngắn nhất**. Nếu một bè bị nốt kế tiếp cùng bè chặn thì bè đó dừng ở nốt kế tiếp; không kéo dài chồng lên nốt mới.

---

## 1. Hiện trạng đo được

### 1.1. Đo trên ACB 1M II (3/4, 96 BPM, 108 ô)

Script: `backend/tmp/diag_fan_ring.py` (đã có, untracked). In mọi ô có nốt rơi vào `0 < beat < 0,25` — tức cú quạt. Số đo dưới đây lấy từ `render()` (đã qua sóng, **chưa** qua `humanize`).

Có **13 ô quạt**. Tất cả đều **5–6 dây**, tức đều là **Loại 1**. Tất cả đều kết thúc đúng `0,5` phách:

| Ô | Dây | Lead (beat / dur / vel) | Peak không-phải-quạt | Lead hiện tại |
|---|---:|---|---:|---:|
| 10 | 6 | `0,167 / 0,333 / 43` | 50 | 43 |
| 17 | 6 | `0,167 / 0,333 / 54` | 54 | 54 |
| 23 | 5 | `0,167 / 0,333 / 57` | 73 | 57 |
| 31 | 6 | `0,167 / 0,333 / 51` | 51 | 51 |
| 36 | 6 | `0,167 / 0,333 / 53` | 53 | 53 |
| 40 | 6 | `0,167 / 0,333 / 55` | 55 | 55 |
| 44 | 6 | `0,167 / 0,333 / 47` | 53 | 47 |
| 70 | 6 | `0,167 / 0,333 / 54` | 50 | 54 |
| 76 | 6 | `0,167 / 0,333 / 57` | 54 | 57 |
| 80 | 6 | `0,167 / 0,333 / 47` | 56 | 47 |
| 87 | 6 | `0,167 / 0,333 / 50` | 66 | 50 |
| 91 | 6 | `0,167 / 0,333 / 57` | 55 | 57 |
| 96 | 6 | `0,167 / 0,333 / 43` | 53 | 43 |

Hai kết luận đo được:

- **Độ dài**: mọi bè đều `0,5` phách. Lead `0,167 + 0,333 = 0,5`; support `0,083 + 0,417 = 0,5`; bass `0,0 + 0,5 = 0,5`.
- **Độ to**: lead của cú quạt **thường thấp hơn** nốt to nhất trong cùng ô (ô 10: `43` so với `50`; ô 44: `47` so với `53`; ô 80: `47` so với `56`; ô 87: `50` so với `66`). Vì vậy tai nghe "có quạt nhưng chưa rõ".

### 1.2. Đo "còn chỗ ngân" của từng bè

Cùng script, cột `v1/v2/v3 -> …`:

- **Lead**: ô nào cũng có nốt kế tiếp đúng `0,5` phách (nốt lặp `staccato` của `CASTILLO_WALK`). Lead **không còn chỗ** để ngân dài hơn trong ô.
- **Support**: **không có** nốt support nào khác trong ô → còn chỗ tới vạch nhịp.
- **Bass**: **không có** nốt bass nào khác trong ô → còn chỗ tới vạch nhịp.

Tức là trên ACB 1M II, cú quạt **không vang thêm** vì cả ba bè bị cắt cứng ở `0,5`, dù bass và support còn trống nguyên ô.

### 1.3. Đường code đang quyết định

- `guitar_torroba.py`:
  - `_stamp_rasgueado()` đặt `releases = {3: 0.5, 2: 0.5, 1: lead_release}`.
  - `_open_rasgueado()` cũng đặt `releases = {3: 0.5, 2: 0.5, 1: lead_release}`.
  - Mọi chỗ gọi đều truyền `lead_release=0.5`, trừ `_type7_bar5()` truyền `lead_release=pen.beats`.
  - Các chỗ gọi Loại 1: `_render_fandanguillo_bar()` (qua `_stamp_rasgueado`), `_render_type2()` khi `pattern == "fandanguillo"`, `_type5_fan()`, `_castillo_walk_fan()`.
  - Các chỗ gọi Loại 2: `_render_type2()` khi `pattern != "fandanguillo"` (sonatina), `_type3_motif()`. `_type7_bar5()` là ca đặc biệt: `max_notes=4` nhưng `accent=True` và lead ngân cả ô.
- `_Pen._local_lead()` kéo mọi velocity lead viết bên trong figure về `lead_level()` của đúng móc đó. Vì vậy **không thể** tăng velocity ngay trong `_stamp_rasgueado()` / `_open_rasgueado()` — sẽ bị ghi đè.
- `guitar_wave.apply_guitar_wave()` cộng một center cho cả ô rồi **kẹp `min(spot.v_ceil, raw)`**. Trần `v_ceil` của `castillo` / `sonatina` là `58`, của `fandanguillo` / `danza` / `alcaniz` / `olite` là `63`. Vì vậy tăng velocity **trước** sóng cũng có thể bị kẹp mất phần tăng.
- `musicxml._rasgueado_kind()` chỉ nhận đúng hai trường hợp: lead `4/12`, support `5/12`, hoặc bản ngân hết ô (`bar_units - 2` / `bar_units - 1`). Không có độ dài trung gian.
- `humanize._is_rasgueado()` chỉ đọc **onset** (`0 < beat < 0,25`), nên đổi độ dài không làm hỏng nhận diện quạt.
- `assert_playable()` (profile `torroba`):
  - Trong cửa sổ quạt (`when % (epb*6) < 6`, tức 6 twelfth đầu ô) cho phép tối đa 6 tiếng, bass 2, support 3.
  - **Ngoài** cửa sổ đó chỉ cho **1 nốt mỗi bè** và tối đa 4 tiếng. Vì vậy hai nốt cùng bè chồng nhau ở `0,5+` sẽ bị từ chối (`two notes in the high voice` / `too many notes in one voice`).

---

## 2. Nguyên nhân

1. **Độ ngân**: `releases` bị đóng cứng ở `0,5` phách. Không có tầng nào nới duration sau khi figure viết xong.
2. **Độ to**: velocity viết bị `_Pen._local_lead()` chuẩn hoá, bị `apply_guitar_wave()` kẹp ở `v_ceil`, rồi bị `humanize._clamp_guitar()` gom vào dải `<= 64` hoặc `69–73`. Không có tầng nào **so với phần còn lại của ô** để bảo đảm cú quạt là tiếng to nhất.
3. **Ký âm**: `musicxml._rasgueado_kind()` không có dạng "ngân một phần ô", nên kể cả có nới duration cũng không engrave được.

Ba nguyên nhân này độc lập; sửa một cái không đủ.

---

## 3. Quy tắc mới — độ ngân

### 3.1. Nhận diện cú quạt sau pipeline

Thêm helper trong `guitar_torroba.py`:

```python
def _fan_shape(ctx, bar, lead, support, low) -> tuple[str, dict[int, list[NoteEvent]]] | None:
    """'strong' (5–6 dây) / 'soft' (3–4 dây), và ba bè của cú quạt. None nếu không phải quạt."""
```

- Một ô là ô quạt khi có ít nhất một nốt `midi is not None` với `0 < beat < 0,25` trong `lead` hoặc `support`.
- Gom các nốt trong `[0, 0,25)` theo `voice` (1, 2, 3).
- `strong` khi tổng số cao độ trong cửa sổ `>= 5`; ngược lại `soft`. Một thế bấm hẹp của Loại 1 chỉ ra 4 dây sẽ được xử như Loại 2 — chấp nhận được vì chênh lệch giữa hai loại chỉ là "một chút".
- Không dùng `id()` hay marker trên `NoteEvent`: `_resolve()` / `_spell16()` tạo lại event nên marker sẽ mất.

### 3.2. Điểm kết thúc

Với từng bè `v ∈ {lead, bass, support}`:

```text
room(v) = beat của nốt kế tiếp cùng bè trong cùng ô, hoặc bar_beats nếu không có
end(v)  = min(room(v), bar_beats, CAP[kind][v])
```

- `CAP` tính bằng **twelfth** (divisions = 12, 1 phách = 12 twelfth).
- Chỉ **nới**, không bao giờ thu: nếu `end(v) <= beat(v) + duration(v)` thì giữ nguyên.
- **Làm tròn xuống bội `3/12`**: `end = floor(end * 12 / 3) * 3 / 12`. Bắt buộc, không chỉ là "cho đẹp": đuôi tie phải là `3/12`, `6/12`, `12/12`; nếu rơi vào `2/12`, `_is_sixth()` sẽ coi đó là sextuplet và `_note_type()` có thể raise. Đây là guard cứng.
- Nếu nốt kế tiếp cùng bè nằm trước `0,5` thì bỏ qua (không nới), vì duration hiện tại đã chồng — đó là lỗi playability có sẵn, không phải việc của đợt này.

**Không thể nới cả cụm support.** `assert_playable()` kiểm tra thứ tự bè khi các nốt cùng vang. Trên ACB 1M II, ô 40 có support cao nhất `74` nhưng nốt lead kế tiếp ở `0,5` là `71`: nếu cả cụm support ngân qua `0,5`, `max(mids) >= min(highs)` → `inner voice is not below the melody`. Vì vậy chỉ **một nốt support** được giữ tiếng.

Chọn nốt giữ tiếng:

| Bè | Nốt giữ tiếng | Lý do |
|---|---|---|
| **lead** | nốt duy nhất | chỉ có một |
| **bass** | **cả cụm** (1–2 nốt, thường quãng tám) | MuseScore chuẩn hoá chord về duration của nốt đầu, nên hai nốt bass phải cùng duration; cả hai đều là gốc, ring cùng nhau là đúng |
| **support** | cao độ **thấp nhất** | ở dưới melody, tránh `inner voice is not below the melody`; các nốt support còn lại cắt `0,5` |

**Ký âm support**: head chord vẫn đều `5/12` cho cả cụm; chỉ nốt thấp nhất có thêm **đuôi tie** (`_add_plain_tail([lowest])`). Nhờ vậy chord không có duration lệch — đúng điều MuseScore cần (xem 5.5).

**Ký âm bass**: vì bass bắt đầu ở `0,0` (không phải nốt quạt), cả cụm bass nhận **cùng một duration** mới (plain `1/4` hoặc dotted `1/8`). Không có chord lệch duration.

Bảng đề xuất:

| Loại | lead | bass (cả cụm) | support (nốt thấp nhất) |
|---|---:|---:|---:|
| **1 — attack** | `18/12` = `1,5` phách | `12/12` = `1,0` | `9/12` = `0,75` |
| **2 — mềm** | `12/12` = `1,0` | `9/12` = `0,75` | `6/12` = `0,5` (giữ nguyên) |

Vì sao các con số này:

- Đều là bội của `3/12`, nên phần đuôi nối tie rơi vào các giá trị ký âm sạch (`3/12` = móc kép, `6/12` = móc đơn, `12/12` = nốt đen).
- Trên ACB 1M II, lead bị chặn ở `0,5` (nốt lặp), nên thực tế **bass `0,5 → 1,0`** và **support `0,5 → 0,75`**. Cú quạt vang gấp đôi ở bass — đủ nghe rõ, không thành pedal.
- Ở `fandanguillo`, lead có nốt kế tiếp ở `1,0`, nên lead thực tế `0,5 → 1,0`; bass `→ 1,0`; support `→ 0,75`.
- Loại 2 giữ support ở `0,5`: bè trong không cần ngân, tránh bùn. Chênh lệch Loại 1 / Loại 2 nằm ở lead và bass.

### 3.3. Cửa sổ `assert_playable` phải phủ hết cú ngân

Với bass 2 nốt cùng ngân qua `0,5`, kiểm tra hiện tại báo `two bass notes are the tremolo exception` vì ngoài 6 twelfth đầu chỉ cho 1 bass. Vì vậy phải nới **cửa sổ quạt** (không nới ngưỡng đếm):

```python
fan_bars = {
    event.bar
    for events in (score.lead, score.support)
    for event in events
    if event.midi is not None and 0.0 < event.beat < 0.25
}
roll_window = profile == "torroba" and (
    (bar in roll_bars and (when % (epb * 6)) < 6)
    or (bar in fan_bars and (when % (epb * 6)) < 12)
)
```

- Bar có cú quạt: cửa sổ **6 → 12 twelfth** (nửa phách → một phách).
- Bar `roll_bar` không có cú quạt (sextuplet, mordent…): giữ nguyên `< 6` như cũ. Không nới bừa.
- Ngưỡng đếm giữ nguyên: tối đa 6 tiếng, 2 bass, 3 support, 1 high. Nhờ vậy một attack **mới** chen vào khi hợp âm đang ngân vẫn bị bắt (ví dụ bass thứ 3).
- Kiểm tra thứ tự bè giữ nguyên, nên support ring vẫn phải nằm dưới melody.
- `lead` Loại 1 có thể ngân tới `1,5`; sau `1,0` chỉ còn một nốt high, nên luật chặt phía ngoài cửa sổ vẫn đúng.

### 3.4. Chặn theo chiều dọc

Ngoài `room(v)`, mỗi nốt giữ tiếng còn phải dừng trước nốt nào làm vỡ thứ tự bè:

```text
end(lead)    = min(end(lead),    beat của nốt đầu tiên sau đó ở bè khác có midi >= lead_pitch)
end(bass)    = min(end(bass),    beat của nốt đầu tiên sau đó có midi < bass_pitch)
end(support) = min(end(support), beat của nốt lead đầu tiên sau đó có midi < support_pitch)
```

- `lead` **cũng cần guard**: fixture 6/8 fandanguillo bar 0 có lead `2/12 midi 64` và support `0,5 midi 64`. Nếu lead nới tới `1,0`, tại `when = 6..11` có `highs = {64}`, `mids = {64}` → `inner voice is not below the melody`. Phải dừng lead trước nốt support/bass đầu tiên có `midi >= lead_pitch`.
- `bass` luôn là bè thấp nhất; nốt làm vỡ thứ tự chỉ có thể là một nốt rất thấp khác, hiếm.
- `support` chọn nốt thấp nhất, nên chỉ cần chặn khi melody xuống dưới nó. Đây là guard bắt buộc: không có nó, ô 40 kiểu ACB sẽ fail.

### 3.5. Thứ tự ưu tiên

- Khi cả ba bè đều còn chỗ, `CAP` đã bảo đảm `lead ≥ bass ≥ support` cho **nốt giữ tiếng**.
- Khi một bè bị nốt kế tiếp chặn, bè đó dừng sớm hơn; **không** kéo bass/support xuống theo. Đây là ngoại lệ có chủ đích: trên guitar thật, dây trầm vẫn ngân dưới nốt lặp của bè cao.
- Support chỉ giữ **một** nốt; các nốt support còn lại cắt `0,5`. Bass giữ **cả cụm** vì chúng cùng duration và cùng là gốc.

---

## 4. Quy tắc mới — độ to

### 4.1. Nguyên tắc phân tầng

`humanize` hiện **không chỉ** là "cơ thể": nó đã có ba tầng **style** (phrase arc, bar lean, lilt) và một ràng buộc **timbre** (`_clamp_guitar`, dải ấm/móng). Nguyên tắc của đợt này là: **không thêm quyết định âm nhạc mới vào cuối humanize**; chỉ thêm một tầng **cơ thể** (`fan_hold`) vào chỗ tempo clock đã có, và giữ các tầng style cũ nguyên vẹn.

Bảng phân tầng, tách rõ "quyết định" và "ánh xạ kỹ thuật":

| Việc | Phần âm nhạc (quyết định) | Phần kỹ thuật (ánh xạ) | Tầng |
|---|---|---|---|
| Voicing, accent | hợp âm nào, dây nào | thế bấm, `_playable` | figure |
| Ngân | ngân tới nốt kế / vạch nhịp theo vai trò | CAP tay, room cùng bè, floor `3/12` | score (ring) |
| To | quạt nổi hơn nền `+3/+2` | dải ấm `<= 64` hoặc móng `73 / 71 / 69` | dynamic pass (`_apply_fans`) |
| Trễ | `D = 1/12` / `1/24` (lượng do style) | nguyên nhân: chuyển thế bấm; ánh xạ: tempo dip | humanize (`fan_hold`) |
| Bar lean / lilt | style Torroba | — | humanize (đã có) |
| Micro ±2 | — | dao động cơ thể | humanize (đã có) |

Vì vậy "to" vẫn ở tầng dynamic, "trễ" ở humanize, còn các tầng style cũ **không bị di chuyển**. Đây là lý do không đặt `_apply_fans` trong `humanize`: làm vậy là thêm một quyết định âm nhạc vào tầng style/cơ thể, đúng thứ cần tránh.

### 4.2. Vì sao tầng dynamic, không phải humanize

Ba tầng phía trước đều bóp méo velocity của cú quạt:

- `_Pen._local_lead()` ghi đè velocity viết bên trong figure.
- `apply_guitar_wave()` kẹp `min(v_ceil, raw)`; trần `58` / `63` làm phần tăng trước sóng biến mất.
- `humanize._clamp_guitar()` gom nốt `> 64` vào dải móng `69–73`.

Tầng đúng là một **dynamic pass** đặt **sau `apply_guitar_wave()` và sau hai restamp**, trước humanize. Nó không nằm trong `humanize`, và cũng **không** nằm trong `apply_guitar_wave()` — vì `restamp_passage_hairpins()` chạy sau đó có thể `_install_lead()` lại lead của một scale passage trùng ô quạt và ghi đè dynamic vừa đặt.

Thứ tự stage:

```text
apply_guitar_wave()
  → _restamp_swarm_hairpins()
  → restamp_passage_hairpins()
  → _omit_support_under_lowered_lead()
  → _apply_fans()
  → divisions / return
```

`_apply_fans` là writer velocity cuối cùng **trước humanize**, nên không bị restamp ghi đè.

### 4.3. Luật `_apply_fans`

Thêm trong `guitar_wave.py`:

```python
def _apply_fans(ctx, voices, patterns):
    """Đặt dynamic cho toàn bộ nốt quạt, sau wave + restamp."""
```

Gọi từ `guitar_patterns.render_patterned_voices()` ở vị trí trong 4.2.

Với mỗi ô quạt:

```text
fan_notes = TOÀN BỘ nốt trong [0, 0.25) của ô: 1 lead, tối đa 3 support, tối đa 2 bass
peak      = max(velocity của mọi nốt NGOÀI fan_notes trong ô)
lead_now, bass_now, support_now = velocity hiện tại của từng bè quạt

lead_t = max(lead_now, peak + MARGIN[kind])

layer = "warm" if lead_t <= 64 and max(bass_now, support_now) <= 64 else "nail"

if layer == "warm":
    lead    = lead_t
    bass    = max(bass_now, lead - 4)
    support = max(support_now, min(bass - 2, lead - 6))
else:
    # dải móng chỉ có 69–73; 3 bè với khe 2 => 73 / 71 / 69
    lead, bass, support = 73, 71, 69
```

- `fan_notes` là **cả cụm**, không phải "ba nốt": 3/4 Castillo và 6/8 Fandanguillo có thể có 1 lead + 3 support + 2 bass = **6 nốt**. Tất cả bass nhận `bass`, tất cả support nhận `support`, lead nhận `lead`.
- `peak` loại **toàn bộ** `fan_notes`, nếu không cú quạt tự so với chính nó.
- `layer` guard: nếu `bass_now`/`support_now` đã ở `65–68` (do `_apply_stabs` ở pedal/frame), cả cụm vào dải móng — không tạo giá trị lửng.
- `lead_t > 64` → dải móng `73 / 71 / 69`. Sau affine/snap, lead quạt tối đa `73`, bass/support tối đa `63`, nên ba giá trị tuyệt đối này **không hạ** nốt nào.
- Bất biến `lead > bass > support`, khe `>= 2` được bảo đảm bởi công thức.
- **Pin**: sau khi đặt, gắn `pinned=True` cho mọi `fan_notes`. Humanize bỏ qua nốt `pinned` (không nudge, không `_clamp_guitar`), nên thứ tự `73 / 71 / 69` không thể bị `±2` làm thành `71 / 69 / 69`. Xem 4.5.

Bảng đề xuất:

| Loại | `MARGIN` | Ghi chú |
|---|---:|---|
| **1 — attack** | `+3` | vào dải móng khi `lead_t > 64` |
| **2 — mềm** | `+2` | thường ở lại dải ấm; chỉ vào móng khi nền ô đã `>= 63` |

- `lead_t` bảo đảm cú quạt không thấp hơn nền: `>= peak + MARGIN`.
- `bass` / `support` **khôi phục độ dày của hợp âm** chứ không chỉ dịch đều: nếu sóng đã kẹp bass/support xuống quá thấp (như ô 70: `54 / 40 / 32`), `_apply_fans` kéo chúng lên `lead - 4` / `lead - 6` để cả cú quạt cùng to, không bị "đầu voi đuôi chuột".

### 4.4. Pin và thứ tự sau humanize

Đây là hệ quả trực tiếp của việc chuyển dynamic sang trước humanize. `humanize._clamp_guitar()` map mọi nốt `> 64` vào `69–73`:

```text
viết 73 / 71 / 69, nudge bass −2, support −2
→ heard 73 / 69 / 67
→ clamp 73 / 69 / 69   # bass = support, mất khe
```

Nếu không xử lý, §10 "khe >= 2" chỉ đúng **sau wave**, còn score audio/DFI thấy sau humanize thì khe có thể về 0.

Cách chọn: **pin**. Thêm field `pinned: bool = False` vào `NoteEvent`; `_apply_fans` set `pinned=True` cho mọi nốt quạt. Trong humanize:

- `_apply()`: nếu `note.pinned`, giữ nguyên velocity, không cộng offset.
- `_clamp_guitar()`: nếu `note.pinned`, giữ nguyên (cùng nhánh với `hairpin`).

Đây không phải "humanize quyết định dynamic" — ngược lại, nó **tôn trọng** dynamic đã viết ở tầng trước. Pin là hợp đồng "velocity này là cuối", giống `hairpin` đang làm cho scale/swarm. Nhờ vậy `lead > bass > support`, khe `>= 2` sống tới MusicXML. Test phải khẳng định **sau `humanize_score()`**, không chỉ sau wave.

### 4.5. Kết quả dự kiến trên ACB 1M II (Loại 1, `MARGIN = 3`)

> Bảng dưới tính trên số đo **sau wave, trước `_apply_fans`** ở mục 1.1. Sau khi implement, `render()` sẽ trả score **đã có** fan dynamic; muốn đối chiếu phải đo trước `_apply_fans` bằng script nội bộ (tạm bỏ lời gọi trong `render_patterned_voices`). Các ô rơi vào dải móng dùng `73 / 71 / 69`; các ô còn lại ở dải ấm.

| Ô | Lead trước `_apply_fans` | Bass / Support trước | Peak | Lead target | Sau `_apply_fans` (pin) |
|---|---:|---|---:|---:|---|
| 10 | 43 | 43 / 41 | 50 | 53 | 53 / 49 / 47 |
| 17 | 54 | 50 / 42 | 54 | 57 | 57 / 53 / 51 |
| 23 | 57 | 57 / 49 | 73 | 76 | 73 / 71 / 69 (móng) |
| 31 | 51 | 45 / 37 | 51 | 54 | 54 / 50 / 48 |
| 36 | 53 | 52 / 44 | 53 | 56 | 56 / 52 / 50 |
| 40 | 55 | 55 / 47 | 55 | 58 | 58 / 55 / 52 |
| 44 | 47 | 46 / 44 | 53 | 56 | 56 / 52 / 50 |
| 70 | 54 | 40 / 32 | 50 | 54 | 54 / 50 / 48 |
| 76 | 57 | 50 / 42 | 54 | 57 | 57 / 53 / 51 |
| 80 | 47 | 45 / 40 | 56 | 59 | 59 / 55 / 53 |
| 87 | 50 | 46 / 38 | 66 | 69 | 73 / 71 / 69 (móng) |
| 91 | 57 | 53 / 45 | 55 | 58 | 58 / 54 / 52 |
| 96 | 43 | 41 / 38 | 53 | 56 | 56 / 52 / 50 |

Tức là cú quạt **không bao giờ thấp hơn nền**, thường cao hơn `3` đơn vị, và cả ba bè cùng dày lên. Ở các ô nền đã ở dải móng, cú quạt cũng ở dải móng (`73 / 71 / 69`). Giá trị này **pin** qua humanize, nên bảng cũng là kết quả sau `humanize_score()`.

---

## 5. Tầng ký âm (`musicxml.py`)

### 5.1. Tổng quát hoá `_rasgueado_kind()`

Thay hàm nhận diện cứng bằng:

```python
def _rasgueado_span(event, divisions, bar_beats) -> tuple[str, int] | None:
    """('lead' | 'support', sounding_units) cho nốt quạt trong nửa phách đầu."""
    if divisions != 12 or event.midi is None or event.beat >= 0.25:
        return None
    beat_units = round(event.beat * 12)
    duration_units = round(event.duration_beats * 12)
    if beat_units == 2 and duration_units >= 4:
        return ("lead", duration_units)
    if beat_units == 1 and duration_units >= 5:
        return ("support", duration_units)
    return None
```

- `duration_units == 4` (lead) / `5` (support) → đường plain như hiện tại.
- `duration_units > 4` / `> 5` → **head + đuôi tie**:
  - lead: head `4/12` (`tie_start=True`), đuôi `_add_plain_tail(remaining=duration_units - 4)`.
  - support: head `5/12`, đuôi `_add_plain_tail([lowest_support], remaining=duration_units - 5)` — **chỉ nốt support thấp nhất** nhận đuôi. Head của cả cụm vẫn đều `5/12`; các nốt còn lại không có đuôi và dừng ở `6/12`.
- **Điều kiện chia 3**: vì ring floor về bội `3/12`, `duration_units` phải là `4 + 3k` (lead) hoặc `5 + 3k` (support). Thêm guard trong `_rasgueado_span()`:
  - lead: `(duration_units - 4) % 3 == 0`
  - support: `(duration_units - 5) % 3 == 0`
  Nếu không, trả `None` (hoặc assert) để không bao giờ đẩy `2/12` vào `_is_sixth()`.
- **Group cùng beat**: vòng lặp hiện tại gom mọi nốt cùng `beat` thành một group rồi đọc `kind` từ nốt đầu. Phải đổi thành đọc **`duration_units` lớn nhất trong group** (nốt giữ tiếng), rồi:
  - nếu `> 5` (support) → head chord đều `5/12` + đuôi cho đúng nốt có duration lớn nhất (đã chọn là nốt thấp nhất);
  - nếu tất cả `== 5` → đường plain như cũ.
- **Lead group phát toàn bộ**: head `4/12` cho **mọi** nốt trong group (giữ `<chord/>` và `tuplet`), nốt nào `> 4` nhận tail. Chord lệch duration bị chuẩn hoá về nốt dài (MuseScore), có test khóa cả cùng-duration và mixed-duration tại `2/12`.
- **Bar-long support nhiều nốt**: chỉ carrier nhận outgoing tie; các nốt còn lại dừng ở `6/12`. Đây là chủ ý; hiện production chỉ có lead bar-long (type 7) nên chưa lộ.
- **`_add_tied_fifth` phải nhận per-note `continues`**, không phải `continue_after: bool` cho cả cụm. Với partial tail, chỉ nốt giữ tiếng nhận `tie start`; các nốt support còn lại chỉ `tie stop` (không treo tie). Xem 5.4.
- Bản ngân hết ô hiện tại (`bar_units - 2` / `bar_units - 1`) tự động rơi vào cùng công thức, nên **không cần nhánh riêng**.
- Hàm cũ `_rasgueado_kind()` vẫn có thể giữ làm wrapper mỏng cho test cũ, hoặc đổi tên và cập nhật test.

### 5.2. Nhận diện "nốt quạt" cho rest trước nó

`_rasgueado_kind(nxt)` đang được dùng để quyết định rest `2/12` / `1/12` trước cú quạt (nhánh `_add_triplet_rest` / `_add_32nd_triplet_rest`). Phải đổi sang `_rasgueado_span(nxt)` và kiểm tra **role**, không kiểm tra duration. Nếu không, một lead dài `10/12` sẽ rơi vào nhánh `<forward>` và làm mất bracket 3:2 → MuseScore từ chối ô.

### 5.3. Đuôi tie

`_add_plain_tail()` đã có sẵn và đã xử lý chuỗi tie (`tie_stop=True`, `tie_start=not last`). Chỉ cần truyền `remaining` mới:

| Bè | End | Duration | Head | Đuôi |
|---|---:|---:|---:|---:|
| lead | `18/12` | `16/12` | `4/12` | `12/12` (nốt đen) |
| lead | `12/12` | `10/12` | `4/12` | `6/12` (móc đơn) |
| lead | `9/12` | `7/12` | `4/12` | `3/12` (móc kép) |
| support (nốt thấp nhất) | `12/12` | `11/12` | `5/12` | `6/12` |
| support (nốt thấp nhất) | `9/12` | `8/12` | `5/12` | `3/12` |
| bass (cả cụm) | `12/12` | `12/12` | — | plain `_note_type(1.0)` |
| bass (cả cụm) | `9/12` | `9/12` | — | plain `_note_type(0.75)` |

Tất cả đuôi đều là `3/12`, `6/12`, `12/12` → `_note_type()` xử lý sạch, không rơi vào nhánh `[1] * left` (chuỗi 32nd).

### 5.4. Tương tác với `_fill` / `_resolve`

- `_resolve()` bỏ qua event không nằm trên lưới móc kép (`not _on_sixteenth_grid`). Lead ở `2/12`, support ở `1/12` là "odd" → **không bị cắt**.
- Bass ở `0,0` nằm trên lưới → `_resolve()` cắt về nốt kế tiếp cùng bè. Đúng bằng `room(bass)` đã tính, nên không đổi gì.
- `_fill_twelfths()` bỏ event có `start < cursor`. Vì `end(v) <= room(v)`, không có event nào bị bỏ.
- `assert_playable()`: cửa sổ quạt mở tới 12 twelfth cho bar có quạt (mục 3.3), nên bass 2 nốt ngân qua `0,5` vẫn hợp lệ. Các ngưỡng đếm (6 tiếng, 2 bass, 3 support) và kiểm tra thứ tự bè vẫn giữ.

### 5.5. Bằng chứng: MuseScore chuẩn hoá chord lệch duration

Đã thử trực tiếp: một ô `divisions=12` có chord 2 nốt cùng beat, nốt dưới `duration=12`, nốt trên `<chord/>` `duration=6`. Sau khi qua `mscore -o out.musicxml`, **cả hai nốt đều thành `duration=1` (quarter)** — nốt trên bị kéo dài bằng nốt dưới. Vì vậy:

- **Không** dùng chord lệch duration cho bass. Cả cụm bass phải cùng duration.
- Với support, head của cả cụm đều `5/12`; chỉ **đuôi tie** (một nốt riêng, không phải `<chord/>`) thuộc nốt thấp nhất. Nhờ vậy không có chord lệch duration.

### 5.6. Rủi ro ký âm

- **Bắt buộc floor `3/12`**: nếu `end` không phải bội `3/12`, đuôi có thể là `2/12` → `_is_sixth()` coi là sextuplet, hoặc `1/12`/`4/12` sinh chuỗi 32nd. Ring phải floor trước khi ghi; `_rasgueado_span()` có guard `(duration - head) % 3 == 0`. Không chấp nhận "chuỗi 32nd" như bản cũ.
- `_add_tied_fifth()` phải per-note `continues`: nốt không giữ tiếng chỉ nhận `tie stop`, không nhận `tie start` treo. Xem 5.1/5.4.
- `audio.py` đã có fallback khi file `.mscz` do MuseScore lưu bị lỗi tuplet; đuôi tie không tạo thêm tuplet nên không chạm fallback này.

---

## 6. Vị trí trong pipeline

Ba tầng, đúng thứ tự stage:

```text
score:   _repair → apply_torroba_fan_ring → apply_sonatina_downbeats → _resolve → _fill
dynamic: apply_guitar_wave → restamp swarm → restamp passage → omit support → _apply_fans
human:   humanize (_clamp_guitar → fan_hold tempo → micro ±2)
```

1. **`apply_torroba_fan_ring()`** — trong `guitar_patterns.render_patterned_voices()`.
   - Đặt **sau `_repair()`**, **trước `apply_sonatina_downbeats()`** (và trước `_resolve()`).
   - Lý do: `_repair()` có thể cắt support/bass; ring phải là bước cuối cùng quyết định duration. `_resolve()` / `_fill()` sau đó chỉ kiểm tra lại, không phá.
   - Chỉ chạy khi `ctx.ensemble == "torroba"`.
   - Đây là tầng **score** (giá trị nốt viết), không phải humanize.
2. **`_apply_fans()`** — trong `guitar_wave.py`, gọi từ `render_patterned_voices()` **sau `apply_guitar_wave()` và sau hai restamp + `_omit_support_under_lowered_lead()`**, trước khối `divisions`.
   - **Không** gọi bên trong `apply_guitar_wave()`: `restamp_passage_hairpins()` chạy sau đó có thể `_install_lead()` lại lead của scale passage trùng ô quạt.
   - Đây là **writer velocity cuối cùng trước humanize**; `_apply_fans` gắn `pinned=True` cho nốt quạt.
   - Chỉ chạy khi `ctx.ensemble == "torroba"`.
3. **`_fan_hold_deltas()`** — trong `humanize._torroba_phrase_tempos()`.
   - Đây là tầng **cơ thể** duy nhất của rasgueado: độ trễ nốt sau. Xem mục 13.

Chữ ký:

```python
# guitar_torroba.py — duration, trước _resolve
def apply_torroba_fan_ring(ctx, lead, support, low, patterns):
    return lead, support, low

# guitar_wave.py — dynamic, sau restamp, trước humanize
def _apply_fans(ctx, lead, support, low, patterns):
    ...

# humanize.py — tempo, sau cap
def _fan_hold_deltas(score, start, end, divisions, start_units, count):
    ...
```

Ngoài ba chỗ trên, còn hai chỗ phải sửa:

- **`assert_playable()`** trong `guitar_patterns.py` — mở cửa sổ quạt từ 6 → 12 twelfth cho bar có cú quạt thật (mục 3.3).
- **`NoteEvent.pinned`** + nhánh pin trong `humanize._apply()` / `_clamp_guitar()` (mục 4.5).

`apply_torroba_fan_ring()` và `_apply_fans()` dùng chung logic nhận diện `_fan_shape()` (đặt trong `guitar_torroba.py`); `_fan_hold_deltas()` dùng `_is_rasgueado()` sẵn có trong `humanize.py`.

---

## 7. Phân loại Loại 1 / Loại 2

| Loại | Nơi gọi | `max_notes` | `accent` | Ghi chú |
|---|---|---:|---|---|
| 1 | `_render_fandanguillo_bar()` khi `rolls` | 6 | `True` | `_stamp_rasgueado` |
| 1 | `_render_type2()` khi `pattern == "fandanguillo"` | 6 | `True` | |
| 1 | `_type5_fan()` | 6 | `True` | |
| 1 | `_castillo_walk_fan()` | 6 | `True` | |
| 2 | `_render_type2()` khi `pattern != "fandanguillo"` | 4 | `False` | `bed_steps=1` |
| 2 | `_type3_motif()` | 4 | `False` | `bed_steps=1` |
| 2 (đặc biệt) | `_type7_bar5()` | 4 | `True` | `lead_release=pen.beats`, đã ngân cả ô |

Lưu ý đo được: **ACB 1M II chỉ có Loại 1** (13/13 cú quạt đều 5–6 dây). Muốn nghe Loại 2 phải test một bản có `sonatina` / `type 3` / `type 7 bar 5`, hoặc dựng fixture trực tiếp.

---

## 8. Ca biên

1. **Quạt hai bè / chỉ lead**: `_rasgueado_onsets()` đã xử lý. Ring chỉ nới bè có mặt; bè vắng không tạo nốt giả.
2. **`_type7_bar5`**: lead đã ngân hết ô (`lead_release=pen.beats`). `end = min(room, bar, CAP)` không được **rút ngắn** nó. Luật "chỉ nới" bảo vệ ca này.
3. **Ô đệm / transition**: nếu cú quạt nằm trong ô đệm (B→A) và `_smooth_boundaries()` đã bỏ attack, ring phải đọc trạng thái **sau** cushion; vì vậy đặt sau `_repair()`. Nếu ô đệm không còn đủ ba bè, `_fan_shape()` trả `None` và không làm gì.
4. **Ô cuối bản**: `bar_beats` vẫn là độ dài ô; ring không vượt vạch nhịp.
5. **`6/8`**: `bar_beats = 3,0`; `CAP` lớn nhất `1,5` vẫn nằm trong ô. Không cần đổi.
6. **Hai nốt bass cùng lúc** (quãng tám): cả hai cùng ngân tới `end(bass)`, cùng duration — vì MuseScore chuẩn hoá chord về duration nốt đầu, không thể cho một nốt dài một nốt ngắn. Cửa sổ quạt đã nới ở 3.3 để cho phép 2 bass cùng vang trong phạm vi cú ngân.
7. **Lead bị chặn ở `0,5`** (castillo walk, type 2/3): giữ nguyên lead; bass/support vẫn nới. Đây là ngoại lệ đã nêu ở mục 3.3.
8. **Quạt ở ô không có nốt nào khác**: `peak` rỗng → `lead_t = lead_now`; bass/support vẫn được kéo lên theo `lead - 4` / `lead - 6` nếu đang thấp hơn. Không lỗi.
9. **`assert_playable()` với support ngân qua `0,5`**: support chỉ có một nốt trong bè, nên `len(mids) <= 1` ở ngoài cửa sổ. Nếu sau này support có nốt mới trước `end`, `room(support)` đã chặn.
10. **Humanize**: `humanize()` chỉ còn làm phần **cơ thể** của quạt — `_fan_hold_deltas` (trễ nốt sau). Dynamic gốc nằm ở `_apply_fans`, **trước** humanize; nốt quạt được `pinned=True` nên `humanize` bỏ qua hoàn toàn (không nudge, không `_clamp_guitar`). Nhờ vậy `lead > bass > support` sống tới MusicXML, không bị `73/71/69 → 71/69/69`.

---

## Thứ tự thực hiện

1. **`musicxml.py`**: tổng quát hoá `_rasgueado_kind()` → `_rasgueado_span()`; đuôi tie cho lead và cho **nốt support thấp nhất**; cập nhật nhận diện rest `2/12` / `1/12`.
2. **`guitar_torroba.py`**: thêm `_fan_shape()` và `apply_torroba_fan_ring()`.
3. **`guitar_patterns.render_patterned_voices()`**: gọi ring sau `_repair()`, trước `apply_sonatina_downbeats()`.
4. **`guitar_patterns.assert_playable()`**: mở cửa sổ quạt 6 → 12 twelfth cho `fan_bars`.
5. **`NoteEvent` + `humanize.py`**: thêm `pinned: bool = False`; `_apply()` / `_clamp_guitar()` bỏ qua nốt `pinned`.
6. **`guitar_wave.py`**: thêm `_apply_fans()`; gọi từ `render_patterned_voices()` **sau** `apply_guitar_wave()` + hai restamp + `_omit_support_under_lowered_lead()`, trước `divisions`. Set `pinned=True` cho nốt quạt.
7. **`humanize.py`**: thêm `_fan_hold_deltas()` và cộng vào `_torroba_phrase_tempos()` sau cap (mục 13).
8. Chạy `backend/tmp/diag_fan_ring.py` trước/sau; thêm test unit + pipeline + ký âm + timing.
9. Nghe ACB 1M II và một bản có Loại 2; chỉnh `CAP` / `MARGIN` / `D` nếu cần.

Mỗi bước chạy test ngay, không gộp. Bước 1–3 làm trước (duration), bước 4 bắt buộc trước khi test full pipeline, bước 5–7 độc lập.

---

## 9. Kế hoạch test

### 9.1. Unit — nhận diện và độ ngân

- `_fan_shape()` trả `None` cho ô không quạt; `strong` cho 5–6 dây; `soft` cho 3–4 dây; quạt hai bè (bass + lead) vẫn nhận.
- `apply_torroba_fan_ring()`:
  - Loại 1, `fandanguillo` 4/4: lead `0,5 → 1,0`; cả cụm bass `→ 1,0`; nốt support thấp nhất `→ 0,75`; các nốt support còn lại giữ `0,5`.
  - Loại 1, `castillo` type 13: lead giữ `0,5` (bị chặn), cả cụm bass `→ 1,0`, support thấp nhất `→ 0,75`, phần còn lại `0,5`.
  - Loại 2, `sonatina` type 2: lead giữ `0,5` (bị chặn), cả cụm bass `→ 0,75`, support giữ `0,5`.
  - Không bao giờ rút ngắn: `_type7_bar5` giữ `duration = bar_beats - 2/12`.
  - Support dừng trước một nốt lead thấp hơn nó (guard 3.4).
  - `assert_playable(..., profiles="torroba")` pass cho cả ba mét, với cửa sổ quạt mở tới 12 twelfth.
- `_fan_shape()` không nhận nhầm nốt mordent / grace ở `0,25` (điều kiện `< 0,25`).

### 9.2. Unit — độ to (tầng dynamic)

- Trên fixture pipeline, dựng một ô có cú quạt + một nốt lead to hơn ở `0,5`; chạy `render_guitar_score()` (đã gồm wave + `_apply_fans`).
- Nhánh ấm (`lead_t <= 64`): `lead == max(lead_now, peak + 3)` (Loại 1) / `+2` (Loại 2); `bass >= lead - 4`; `support >= min(bass - 2, lead - 6)`; mọi giá trị `<= 64`.
- Nhánh móng (`lead_t > 64`): đúng `73 / 71 / 69`.
- **Toàn bộ** nốt quạt nhận mức của bè: 3 support cùng `support`, 2 bass cùng `bass`. `peak` loại toàn bộ chúng.
- `lead > bass > support`, khe `>= 2`.
- Khẳng định ca "bass/support bị sóng kẹp thấp" vẫn được kéo lên (ô 70 kiểu `54 / 40 / 32` → `54 / 50 / 48`).
- **Pin qua humanize**: chạy `humanize_score(score)` rồi so sánh — fan giữ **đúng** `73 / 71 / 69` hoặc đúng mức ấm, không lệch ±2, không bị `_clamp_guitar` kéo `73/71/69 → 71/69/69`.
- **Scale passage + fan bar** (follow-up): thứ tự `_apply_fans` sau restamp đã đảm bảo bằng cấu trúc, nhưng chưa có test riêng; nếu sau này đổi thứ tự, thêm fixture passage đi qua ô quạt.
- Khẳng định các nốt **không thuộc** cú quạt không đổi velocity.

### 9.3. Ký âm

- `score_to_musicxml()` với lead `end = 12/12`: có head `duration=4` + `tie start`, đuôi `duration=6` + `tie stop`; không có `<forward>`; tổng duration đúng bằng ô.
- Support `end = 9/12`: `_add_tied_fifth` cho cả cụm (head `5/12`, không đuôi), **chỉ nốt thấp nhất** có thêm đuôi `3/12`.
- Bass `end = 9/12`: cả cụm một nốt `duration=9`, `type=eighth`, `dot` (hoặc 2 nốt cùng `duration=9` nếu là quãng tám).
- `_assert_complete_tuplets()` vẫn pass (không có `<forward>`, mọi `time-modification` là `3:2` / `6:4`).
- Test cũ `_assert_held_lead_xml` (lead ngân hết ô) phải giữ nguyên kết quả.

### 9.4. Regression

- `pytest backend/tests/test_sonify_guitar_torroba.py -q`.
- `pytest backend/tests/test_sonify_note_surface_grid.py -q` (`_covers12`, `two notes in the high voice`, và test cửa sổ quạt — nay 12 twelfth cho bar có quạt).
- `pytest backend/tests/test_sonify_guitar.py -q`.
- Toàn bộ: `pytest backend/tests -q`.

Các test **pipeline** sẽ đổi kỳ vọng, phải cập nhật có chủ đích:

- `_assert_eighth_roll` (`test_sonify_guitar_torroba.py:2249`) đang assert `lead=68 / bass=64 / support=56` cho `_pattern_score`; sau `_apply_fans` thành `73 / 71 / 69` (hoặc mức ấm). Thêm tham số `fan_velocity` hoặc tách fixture direct-figure.
- `_assert_eighth_xml` đang assert bass `duration=6`, support `5`; sau ring thành `9/12`/tail. Cập nhật theo bảng 5.3.
- `_assert_tied_fifth` đang kỳ vọng tail `["stop"]`; sau per-note `continues` thành `["stop", "start"]` cho nốt giữ tiếng, `["stop"]` cho nốt còn lại.
- Các call pipeline tại `2693` (6/8 fandanguillo) và `2753` (3/4 castillo) bị ảnh hưởng bởi cả ring lẫn `_apply_fans`.
- Test gọi **trực tiếp** `render_torroba_figure()` / `_render_torroba_bar()` vẫn thấy `0,5` và velocity cũ, vì ring là pass của pipeline và `_apply_fans` nằm sau wave. Ghi chú rõ trong test mới, giống cách `_torroba_cushion` đã làm.

### 9.5. Nghe thử

- `backend/tmp/diag_fan_ring.py` trước/sau: in `end` từng bè và `peak` / `target`.
- Render lại ACB 1M II, nghe 13 ô quạt ở mục 1.1.
- Render một bản có `sonatina` / `type 3` / `type 7 bar 5` để nghe Loại 2.

---

## 10. Checklist nghiệm thu

- [ ] Mọi cú quạt Loại 1: **cả cụm bass** dài `>= 1,0` phách khi ô còn chỗ; nốt support thấp nhất `>= 0,75`; lead `>= 0,5` (và `1,0` khi không bị chặn).
- [ ] Mọi cú quạt Loại 2: **cả cụm bass** `>= 0,75`; support thấp nhất `>= 0,5`; lead `>= 0,5`.
- [ ] Các nốt support **không giữ tiếng** vẫn `0,5`; bass giữ cả cụm cùng duration; support chỉ giữ nốt thấp nhất.
- [ ] Support dừng trước nốt lead thấp hơn nó; bass dừng trước nốt thấp hơn nó; **lead dừng trước nốt support/bass có `midi >= lead_pitch`**.
- [ ] Mọi `end` là bội `3/12`; không có đuôi `2/12` (sextuplet) hay chuỗi 32nd.
- [ ] `assert_playable` cho phép bass 2 nốt ngân qua `0,5` trong cửa sổ 12 twelfth của bar quạt, nhưng vẫn bắt attack mới chen vào.
- [ ] Không nốt quạt nào bị **rút ngắn** so với hiện tại.
- [ ] Trong mỗi ô quạt, `velocity(lead)` không thấp hơn nền và `>= peak + 3` (Loại 1) / `>= peak + 2` (Loại 2) khi còn ở dải ấm.
- [ ] Bass/support được kéo lên theo độ dày hợp âm: `bass >= lead - 4`, `support >= min(bass - 2, lead - 6)`.
- [ ] **Toàn bộ** nốt quạt (1 lead, tối đa 3 support, tối đa 2 bass) nhận mức của bè; `peak` loại toàn bộ chúng.
- [ ] `lead > bass > support` với khe `>= 2` **sau `_apply_fans` và sau `humanize_score()`** (pin).
- [ ] Dynamic gốc của quạt nằm ở `_apply_fans` (dynamic pass), **không** ở humanize.
- [ ] Không velocity quạt nào rơi vào `65–68`: hoặc cả cụm `<= 64` (ấm), hoặc đúng `73 / 71 / 69` (móng).
- [ ] Các nốt không thuộc cú quạt giữ nguyên velocity.
- [ ] `assert_playable(..., profiles="torroba")` pass trên toàn bộ fixture Torroba.
- [ ] MusicXML: không `<forward>` trong ô quạt; độ dài các voice cộng đúng bằng ô; mọi `tie start` đều có `tie stop` tương ứng (không treo tie).
- [ ] `_apply_fans` chạy sau `restamp_passage_hairpins`; scale passage trùng ô quạt không ghi đè fan lead.
- [ ] `humanize_score()` **không** đổi velocity của nốt `pinned` (fan), không chỉ "lệch ±2".
- [ ] Nốt **ngay sau** cú quạt vào trễ đúng `1/12` phách (Loại 1) / `1/24` phách (Loại 2), đo bằng tích phân tempo clock.
- [ ] Thời gian kết thúc ô / phrase **không đổi**; `NoteEvent.beat` không đổi, chỉ có `TempoEvent`.
- [ ] Quạt 16th áp cùng `D` như móc đơn; ô không có attack sau thì không sinh tempo event.
- [ ] Toàn bộ test cũ pass; không đổi `spec.bpm`, form, pattern id.

---

## 11. Tài liệu cần cập nhật khi vào code

- [`docs/sonify-guitar-torroba-phrase-plan.md`](./sonify-guitar-torroba-phrase-plan.md) mục 4: bảng Loại 1 / Loại 2 thêm cột "ngân" và "dynamic".
- [`docs/sonify-guitar-torroba-note-surface.md`](./sonify-guitar-torroba-note-surface.md): thêm dạng "held part-bar" (`head + plain tail`), cạnh `held-eighth` / `held-fifth`; **đổi cửa sổ quạt từ 6 → 12 twelfth** cho bar có quạt, kèm lý do (hợp âm ngân qua nửa phách).
- [`docs/sonify-pattern-names.md`](./sonify-pattern-names.md) mục 3: ghi chú rasgueado giờ có thể ngân một phần ô.
- [`docs/sonify-guitar-torroba-dynamics.md`](./sonify-guitar-torroba-dynamics.md): thêm `_apply_fans` ở tầng dynamic (sau wave + restamp, trước humanize), lý do dynamic của quạt là quyết định âm nhạc; `NoteEvent.pinned` và việc humanize bỏ qua nốt quạt.
- [`docs/sonify-guitar-torroba-lilt-accents.md`](./sonify-guitar-torroba-lilt-accents.md): thêm tầng thứ tư `fan_hold` vào mục tempo (ba tầng → bốn tầng), kèm công thức `x = D/(span+D)`, `y = D/(comp-D)` và lý do tầng này nằm sau cap.
- [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 3: cập nhật nếu có bảng duration của roll.
- Ghi chú chung: stage order mới (ring → wave → restamp → `_apply_fans` → humanize).

---

## 12. Rủi ro và rollback

| Rủi ro | Cách chặn |
|---|---|
| Bass ngân quá lâu thành pedal, che hòa âm ô sau | `CAP` bass `1,0` (Loại 1) / `0,75` (Loại 2); không vượt vạch nhịp |
| Hai nốt cùng bè chồng nhau | `end <= room`; test `assert_playable` |
| Mở cửa sổ quạt 6 → 12 làm lọt stack xấu | Chỉ mở cho `fan_bars` (có onset trong `0 < beat < 0,25`), không mở cho mọi `roll_bar`; ngưỡng đếm và kiểm tra thứ tự bè giữ nguyên |
| Chord lệch duration bị MuseScore kéo dài nốt ngắn | Không dùng chord lệch duration: bass cả cụm cùng duration; support chỉ thêm **đuôi tie** cho nốt thấp nhất (đuôi là nốt riêng, không phải `<chord/>`) |
| MuseScore từ chối ô vì tuplet | Giữ rest `2/12` / `1/12` là `<rest>` có 3:2; đuôi tie là nốt plain; floor `3/12` để không sinh `2/12` |
| Dynamic quạt bị humanize sửa | `_apply_fans` gắn `pinned=True`; humanize bỏ qua hoàn toàn nốt pinned |
| Thứ tự `73/71/69` bị nudge làm bằng nhau | Pin (4.5); test post-humanize, không chỉ post-wave |
| Restamp ghi đè fan lead | `_apply_fans` chạy **sau** `restamp_passage_hairpins` / `_restamp_swarm_hairpins` / `_omit_support_under_lowered_lead` |
| Giá trị `65–68` từ `_apply_stabs` | Layer guard: nếu `bass_now`/`support_now` `> 64`, cả cụm vào móng `73/71/69` |
| Bass/support bị "ba nốt" bỏ sót | `fan_notes` là toàn bộ nốt trong `[0, 0.25)`, không phải 3 nốt |
| Lead ngân qua nốt support cùng cao độ | Guard 3.4: lead dừng trước nốt khác bè có `midi >= lead_pitch` |
| Tempo dip 20 % nghe thành "khựng" | Chỉ `4/12` phách; giảm `D` Loại 1 về `1/24` hoặc kéo điểm bắt đầu chậm về `0` (`x` còn `14,3 %`) |
| Tempo dip làm dài phrase | Zero-sum theo thời gian trong từng ô (`+x` rồi `−y`); test thời điểm kết thúc phrase |
| Tempo dip bị cap 10 % bóp mất độ trễ | Cộng `fan_delta` **sau** `scale`, clamp riêng `±25 %` |
| Ảnh hưởng ensemble khác | Ring và `_apply_fans` chỉ chạy khi `ctx.ensemble == "torroba"`; fan_hold chỉ chạy khi `score.variant == "guitar"` và `score.ensemble == "torroba"` |

Rollback: xoá lời gọi `apply_torroba_fan_ring()` trong `render_patterned_voices()`, xoá lời gọi `_apply_fans()` (sau restamp), xoá `_fan_hold_deltas()` khỏi `_torroba_phrase_tempos()`, trả `_rasgueado_kind()` và điều kiện `roll_window` về bản cũ, bỏ field `pinned` và nhánh pin trong humanize, xoá các helper. Field `pinned` có default nên rollback không phá dữ liệu cũ.

---

## 13. Trục 3 — nhịp: nốt ngay sau cú quạt vào trễ

### 13.1. Đặc tính

Sau một cú quạt (nhất là khi cú quạt được ghi là **nốt đen** hoặc **móc đơn**), nghệ sĩ không vào nốt kế đúng phách. Họ mượn thêm một khoảng rất ngắn để tay trái chuyển thế bấm / nhả hợp âm, nên **nốt ngay sau cú quạt vào trễ hơn một chút**, rồi bù lại ở các nốt sau. Đây là agogic/rubato cục bộ, không phải đổi nhịp của cả câu, và **không tỉ lệ với quãng chuyển tay**.

Thông số đã chốt:

| Loại | Độ trễ `D` | Ghi chú |
|---|---:|---|
| **1 — attack** | `1/12` phách | ≈ 52 ms ở 96 BPM |
| **2 — mềm** | `1/24` phách | ≈ 26 ms ở 96 BPM |

- Chỉ **nốt ngay sau** cú quạt bị trễ; các nốt sau bắt lại nhịp.
- Quạt **móc kép** (16th) hiếm, nhưng vẫn xử như móc đơn — áp cùng `D`.
- Không đụng `NoteEvent.beat`: score vẫn nằm trên lưới 12. Độ trễ nằm ở **tempo clock**, không phải ở ký âm.

**Đơn vị và adapt**: `1/12` / `1/24` là ước lượng tại ~96 BPM, **không phải ràng buộc ký âm**. Vì độ trễ nằm ở tempo clock, `D` có thể là số thực bất kỳ — không cần snap về nốt chuẩn. Cách triển khai giữ `D` theo **phân số nốt đen** (`D1 = 1/12`, `D2 = 1/24` phách) vì đơn giản và nhất quán với ba mét `3/4` / `4/4` / `6/8` (trong cả ba, `1,0` trong `bar_beats` là một nốt đen).

Nếu muốn cố định **thời gian vật lý** (tay trái chuyển thế bấm gần như hằng số), quy đổi tại nominal BPM:

```text
D (phách) = D_ms * bpm / 60000
```

| BPM | `D1` (`1/12` phách) | `D2` (`1/24` phách) |
|---:|---:|---:|
| 92 | 54 ms | 27 ms |
| 96 | 52 ms | 26 ms |
| 120 | 42 ms | 21 ms |
| 132 | 38 ms | 19 ms |

Khuyến nghị: giữ dạng **phân số nhịp** (đơn giản, đúng ý "chậm một chút"). Nếu nghe ở tempo nhanh thấy trễ quá ít, chuyển sang dạng `ms` cố định — chỉ đổi một dòng quy đổi, không đổi công thức tempo.

### 13.2. Vì sao dùng tempo dip, không dịch onset

- `1/12` phách nằm đúng trên lưới 12, nhưng `1/24` thì không: `1/24` phách không phải một giá trị nốt chuẩn (nó nằm giữa móc kép và móc ba), muốn ký âm phải mở `divisions = 24` và thêm một nhánh `_note_type` mới — chạm toàn bộ note-surface, `_fill`, `_resolve`, `assert_playable`.
- Tempo dip giữ nguyên grid, xử lý được cả `1/24`, và đúng bản chất: người chơi **không đổi nốt**, họ chỉ ngân cú quạt lâu hơn một nhịp thở rồi mới vào nốt kế.
- `humanize` đã có sẵn ba tầng tempo (`phrase arc`, `bar lean`, `lilt`); thêm tầng thứ tư là đúng chỗ.

### 13.3. Công thức

Thêm `_fan_hold_deltas()` trong `humanize.py`, cùng chỗ với `_bar_deltas()` / `_lilt_deltas()`.

Với mỗi ô quạt trong phrase:

```text
anchor = max(beat của mọi nốt trong cú quạt)   # thường 2/12; dùng khi không có lead
next   = beat của attack đầu tiên sau `anchor` trong cùng ô (bất kỳ bè)
span   = next - anchor
comp   = bar_end - next

T_slow = Σ 1/(1 + base_i) trên các division của [anchor, next)
T_fast = Σ 1/(1 + base_i) trên các division của [next, bar_end)

f = D / (T_slow + D)      # BPM đoạn chậm  *= (1 - f)
g = D / (T_fast - D)      # BPM đoạn nhanh *= (1 + g)
```

- `base_i` là hệ số tempo **đã có** của từng division (phrase arc + bar lean + lilt), không phải 0. Vì vậy phải tính trên `T_slow`/`T_fast` thật, không dùng `span`/`comp` thô — nếu không, độ trễ lệch 10–30 % khi nền đang +5…10 %.
- Trong code, `T_slow`/`T_fast` tính bằng **giây** (`60 / (bpm * 12)` mỗi division) và `delay_seconds = D * 60 / b_local`; công thức `f = D/(T+D)` giữ nguyên, chỉ đổi đơn vị cho khớp.
- `f`, `g` là **hệ số nhân**, không phải cộng vào delta. Tổng thời gian của ô không đổi (zero-sum theo **thời gian**).
- Clamp **`f ≤ 0.25` và `g ≤ 0.25`** (clamp từng hệ số fan), không clamp tổng BPM trước. Khi `g` chạm trần, `f` được tính lại từ phần thời gian `g` thực sự bù được; bar vẫn zero-sum, nhưng **độ trễ thực tế < D** — chấp nhận khi vùng bù quá ngắn.
- Clamp tổng BPM sau đó ở `nominal * [0.60, 1.40]`.
- Nếu `span <= 0`, `comp <= D`, hoặc `span < 3D`: **bỏ qua** ô đó. `span < 3D` là ca quạt 16th / next quá sát; `f` sẽ > 33 % và nghe thành giật, không còn là "một chút".
- Nếu không có lead (quạt hai bè), dùng `anchor = max(beat các nốt quạt)`.
- Hiện mỗi ô chỉ có **một** cú quạt (đúng với pattern hiện tại); `anchor = max(beat các nốt quạt)`. Nếu sau này có hai cú trong một ô, cần xử tuần tự theo từng `anchor` — code hiện chưa làm.

Ví dụ ACB 1M II (3/4, 96 BPM, fan lead `2/12`, next `6/12`, nền ~0):

| Loại | `D` | `span` | `f` | `comp` | `g` |
|---|---:|---:|---:|---:|---:|
| 1 | `1/12` | `4/12` | `20,0 %` | `30/12` | `3,4 %` |
| 2 | `1/24` | `4/12` | `11,1 %` | `30/12` | `1,7 %` |

`f = 20 %` là một cú khựng ngắn (chỉ `4/12` phách). Nếu nghe thành "hiccup", giảm `D` Loại 1 về `1/24` hoặc kéo anchor về `0` (span `6/12` → `f = 14,3 %`). Đây là knob, không phải logic.

### 13.4. Vị trí trong `humanize`

Trong `_torroba_phrase_tempos()`:

```python
bar_delta  = _bar_deltas(...)
lilt_delta = _lilt_deltas(...)
fan_mult   = _fan_hold_multipliers(score, phrase, start, end, divisions, start_units, count)
```

`fan_mult` **không** cộng vào `combined` trước `_TEMPO_CAP`, vì 20 % sẽ kéo cả phrase xuống thang 10 % và làm mất đúng độ trễ. Thay vào đó:

```python
value = phrase_delta + bar_delta[offset] + lilt_delta[offset]
base_bpm = nominal * (1.0 + scale * value)
bpm = base_bpm * fan_mult[offset]          # fan_mult ∈ [0.75, 1.25]
bpm = max(nominal * 0.60, min(nominal * 1.40, bpm))
```

- `fan_mult` là **hệ số nhân** trên BPM đã có `(1 - f)` / `(1 + g)`, clamp từng hệ số ở `[0.75, 1.25]`. Khi `g` chạm trần, `f` được tính lại từ phần thời gian `g` thực sự bù được, để zero-sum vẫn đúng (không làm ô ngắn đi).
- Clamp tổng BPM riêng ở `[0.60, 1.40] × nominal` để không tạo tempo vô lý, nhưng không bóp mất độ trễ fan.
- `fan_mult` zero-sum theo thời gian trong **từng ô**, nên không làm dài phrase.
- Chỉ áp cho ô nằm trọn trong phrase (giống `_bar_deltas`).
- Đây là tầng **cơ thể** nằm trong tempo clock style; ghi rõ ngoại lệ này trong doc `lilt-accents` (mục 11).

### 13.5. Ca biên

1. **Không có attack sau cú quạt trong ô**: bỏ qua.
2. **Attack kế tiếp là bass/support** (không phải lead): vẫn dùng nó làm `next` — đó là nốt người nghe chờ.
3. **Cú quạt ở cuối ô**, `comp` ngắn: bỏ qua nếu `comp <= D`.
4. **`span < 3D`** (quạt 16th, next quá sát): bỏ qua — `f > 33 %` sẽ thành giật, không còn "một chút". Quạt 16th **không** tự động áp `D` nếu span không đủ; đây là điểm sửa so với bản trước.
5. **Không có lead** (quạt hai bè): `anchor = max(beat các nốt quạt)`.
6. **Hai cú quạt trong một ô**: code hiện chỉ xử cú có `anchor` lớn nhất (một cú/ô). Pattern hiện tại không sinh ca hai; nếu cần, mở rộng sau.
7. **Ô đệm / transition**: nếu không còn attack sau cú quạt, bỏ qua.
8. **Tempo dip và độ ngân**: độc lập. Ring đổi `duration_beats`; fan_hold đổi tempo. Không cộng dồn vào cùng một biến.

### 13.6. Test

- Fixture có một cú quạt + nốt kế ở `0,5`:
  - Tích phân thời gian từ `anchor` tới `next` theo tempo clock **thực tế** (đã gồm phrase/bar/lilt) dài hơn nominal đúng `D` phách; sai số ≤ 5 ms hoặc ≤ 10 % của `D` (không dùng 2 ms vì BPM round 2 chữ số).
  - Thời điểm kết thúc ô (và phrase) không đổi so với khi không có `fan_hold`.
  - `NoteEvent.beat` của mọi nốt **không đổi** — chỉ có `TempoEvent` mới.
- Loại 1: `D = 1/12`; Loại 2: `D = 1/24`.
- Quạt 16th: chỉ áp nếu `span >= 3D`; nếu không, không sinh tempo event (mục 13.5).
- Không có attack sau: không sinh `TempoEvent` cho ô đó.
- `comp <= D` hoặc `span < 3D`: bỏ qua, không chia cho 0.
- Hai cú quạt trong một ô: hiện chưa hỗ trợ (một cú/ô); ghi nhận là giới hạn.
- Test cũ của `_torroba_phrase_tempos` (bar lean / lilt) vẫn pass khi không có fan; baseline dùng `D=0` phải trùng khít.

---

## 14. Giai đoạn 2 (tùy chọn, **không** nằm trong đợt này)

`docs/torroba.txt` (dòng 251–253) mô tả mong muốn lý tưởng: **bass dây buông của ô quạt ngân qua cả ô scale kế tiếp**. Đó là một thay đổi khác, cần:

1. Tie **qua vạch nhịp** (hiện `_fill` / `_resolve` cắt ở `bar` và `bar + 1` riêng).
2. `_sounding_bass()` chỉ nhận dây buông `40 / 45 / 50`; bass bấm sẽ không qua cửa.
3. `assert_playable()` phải cho phép bass cũ còn vang khi bass mới vào (hiện `len(lows) > 1` bị từ chối ngoài cửa sổ quạt).
4. `_fill` phải giữ tie qua barline thay vì chèn rest.

Đợt này **không** làm. Nếu nghe thử bản Phase 1 thấy bass cần ngân dài hơn nữa, mở một kế hoạch riêng cho Phase 2; không trộn vào đây để giữ rủi ro nhỏ.

---

## 15. Kết quả triển khai

- `pytest backend/tests -q`: **782 passed**.
- **Cache revision**: `SPAN_REVISION` `71 → 72`, `RECAP_REVISION` `76 → 77` — audio/DFI cũ không replay score cũ.
- ACB 1M II, 13 ô quạt: bass `0,5 → 1,0`; support thấp nhất `0,5 → 0,75`; lead giữ `0,5` (bị nốt lặp chặn); support còn lại giữ `0,5`.
- Dynamic sau `_apply_fans`: các ô ấm `53–59` (lead) / `49–55` (bass) / `47–53` (support); các ô nền móng (`23`, `87`) đúng `73 / 71 / 69`.
- `pinned` giữ nguyên qua `humanize_score()`; thứ tự `lead > bass > support` không bị `_clamp_guitar` làm bằng nhau.
- `fan_hold`: nốt ngay sau quạt trễ đúng `1/12` (Loại 1) / `1/24` (Loại 2) phách; thời lượng ô không đổi.
- **MusicXML lead chord**: nhánh lead phát **toàn bộ** group (không chỉ carrier); chord lệch duration được chuẩn hoá về nốt dài (đúng MuseScore), có test cho cả cùng-duration và mixed-duration tại `2/12`.
- **Partial support XML**: `_assert_tied_fifth(partial=True)` khóa carrier `stop+start`, nốt khác `stop`, tail `3/12` chỉ carrier; test trên 3/4 Castillo.
- **Window test**: đổi tên thành `test_fan_bar_gets_the_whole_first_beat`; thêm `test_a_non_fan_roll_bar_keeps_the_strict_window` (bar odd-grid không có fan vẫn bị luật chặt).
- Test mới: `test_fan_ring_and_dynamic_survive_humanize`, `test_musicxml_keeps_every_lead_note_in_a_chord_at_the_roll_offset`, `test_torroba_fan_hold_delays_only_the_next_attack`, `test_torroba_fan_hold_skips_a_short_span`, `test_torroba_fan_hold_works_without_a_lead`.
- **DFI / tên chương bị "—"**: plan cũ bị HTTP cache giữ lại sau khi audio/DFI được ghi. Đã sửa: `apiGet` dùng `cache: 'no-store'`; `/span` và `/sonify/dfi/pieces` trả `Cache-Control: no-store`; poll reset budget khi bắt đầu phát / audio ready và tăng lên 24 lần (~36 s).
