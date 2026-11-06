# Kế hoạch: đưa pattern + sentences mới vào composer

Trạng thái: đề xuất, chưa triển khai.
Phạm vi: `release/studio-v2.1`; `main` không đổi.
Mục tiêu trước mắt: pattern **Schottish-Choro 2/4** dùng key figure 1 bar + sentences AABA, có flag production.

---

## 1. Kết luận kiểm tra code

### 1.1. Key figure 1 bar

Hiện tại:

- `villa_pattern` có base renderer `_render_villa_bar`, không phải key figure do user chọn.
- `VILLA_ARPEGGIO` là figure 1 bar có sẵn; sau RC6 đã hỗ trợ `2/4`.
- New-pattern draft trả `rhythmTemplate` preview-only; **chưa** được đăng ký thành figure production.

Vì vậy chưa thể “chọn 1 bar bất kỳ làm key figure và loop” trong composer.

### 1.2. Thuật toán sentences

Không có rule **70% sentence / 30% còn lại** trong code.

Đang có:

- `plan_sentence()` / `plan_slots()`:
  - chọn `SentenceSpec` theo `length_min/max`, `n_parity`, `closes`, `rise_min`;
  - tile slots theo `span.tile`;
  - không có tỉ lệ 70/30.
- `guitar_scale_passages.py` có **30% body budget** cho scale passage, không liên quan sentence.

Nếu muốn 70/30 phải định nghĩa rule mới; không nên giả định nó đã có.

### 1.3. Đưa pattern mới vào composer

Composer chỉ đọc:

- `_select_body` / plan rules;
- `SENTENCE_SPECS` đã register;
- pattern renderer code;
- production flag.

Preview/export draft **không đủ**. Cần code + registration + flag + tests.

---

## 2. Hướng triển khai

### Bước A — production trước, key figure có sẵn

Tạo pattern native 2/4:

```text
pattern id: suite_schottish_2_4
meter:      2/4
title:      Schottish-Choro
key figure: VILLA_ARPEGGIO      (1 bar)
contrast:   VILLA_CHORD_MELODY  (1 bar)
sentence:   AABA
```

Sentence:

```text
A = VILLA_ARPEGGIO
B = VILLA_CHORD_MELODY
```

`AABA` tile 4 bar, lặp/truncate theo phrase length.

Ưu điểm:

- dùng `SuiteGate` sẵn có;
- không cần runtime mới;
- composer có pattern thật;
- flag default off, rollback an toàn.

Hạn chế:

- key figure là arpeggio có sẵn, **không** phải đúng rhythm bar người dùng chọn;
- chưa có 70/30;
- chưa phải transcription của bản gốc.

### Bước B — key figure tùy ý từ passage

Sau khi Bước A chạy ổn định:

1. Chọn 1 bar passage.
2. Trích:

```text
role → onset / duration / rest / tie
```

3. Gán pitch policy:

| Role | Policy |
|---|---|
| Lead | `melody_at_beat` / `melody_eighth` |
| Mid | `chord_degree` |
| Bass | `bass_root` / chord root |

4. Tạo `KeyFigureSpec` / `RhythmTemplate` production.
5. Renderer generic loop key figure.
6. Sentence slots override một phần bar.
7. Nếu cần 70/30, định nghĩa rule rõ:

```text
70% bar body = sentence slots
30% bar body = key figure loop
```

Rule 70/30 **chưa có**; chỉ làm khi bạn chốt.

---

## 3. Bước A — chi tiết production

### 3.1. Module mới

```text
backend/app/sonify/guitar_suite_schottish_2_4.py
```

Dùng:

- `SuiteGate`;
- `VILLA_ARPEGGIO`, `VILLA_CHORD_MELODY`;
- `render_villa_figure`;
- `sentence_specs.register`.

Data dự kiến:

```python
PATTERN = "suite_schottish_2_4"
METER = "2/4"
MIN_BARS = 4

SENTENCE = SentenceSpec(
    id="suite_schottish_2_4_aaba",
    pattern=PATTERN,
    meter=METER,
    select=Select(length_min=4),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=2, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=3, bars=1, figure=VILLA_ARPEGGIO),
    ),
)
```

`SuiteGate` hiện đã hỗ trợ meter bất kỳ; `METER_24` đã có trong `form.py`.

### 3.2. Flag

Thêm:

```text
VSTOCK_SUITE_SCHOTTISH_2_4
```

trong `production_flags.py`:

- env reader;
- ContextVar override;
- `suite_schottish_2_4_enabled()`;
- `use_suite_schottish_2_4()`.

Default off.

### 3.3. Selection + render

Thêm module vào:

```text
backend/app/sonify/guitar_suite_movements.py
```

thứ tự precedence:

- `suite_schottish_2_4` trước `suite_schottish` (4/4 stand-in);
- vì khác meter nên không tranh nhau.

`_gated_sentence` đã dùng `suite_movements.render_sentence`; không cần branch riêng.

`_finish_voices` ringing set thêm:

```text
suite_schottish_2_4
```

### 3.4. Pattern metadata

Thêm:

- `PatternMeta` cho `suite_schottish_2_4`;
- `PATTERN_NAMES` / matrix row nếu codegen yêu cầu;
- title `Schottish-Choro`;
- level `topic`, name source `dance`.

### 3.5. Composer output

Khi flag on, với:

```text
ensemble = villa
meter = 2/4
bars >= 4
no pedal bars
```

composer chọn `suite_schottish_2_4` và render AABA.

Key figure loop = các slot A `VILLA_ARPEGGIO`; B là contrast.

### 3.6. Tests

- Flag off: digest byte-identical với historical Villa.
- Flag on:
  - selection trả `suite_schottish_2_4`;
  - render đúng 2/4;
  - plan `AABA`;
  - figure ids đúng;
  - `suite_schottish` 4/4 không bị ảnh hưởng;
  - 2/4 không eligible nếu `<4` bar hoặc có pedal.
- Gate:
  - pin off/on digest;
  - shared tail spy;
  - no registry mutation ngoài context.
- Matrix/codegen:
  - pattern row mới;
  - title coverage;
  - docs §3.2/§12 cập nhật.
- Full backend + frontend.

---

## 4. Bước B — key figure tùy ý

### 4.1. Model

```json
{
  "id": "villa_schottish_key",
  "meter": "2/4",
  "events": [
    {"voice": "lead", "beat": 0, "duration": 1, "policy": "melody"},
    {"voice": "mid", "beat": 0, "duration": 1, "policy": "chord_degree:2"},
    {"voice": "bass", "beat": 0, "duration": 2, "policy": "bass_root"}
  ]
}
```

- `events` là rhythm template.
- `policy` map sang price/chord.
- Không lưu absolute MusicXML MIDI trong production.

### 4.2. Renderer

Thêm materializer generic:

```text
render_rhythm_template_bar(ctx, bar, template)
```

- Lead: `melody_at_beat` / `melody_eighth`;
- Mid: `chord_degree`;
- Bass: `bass_root`;
- loop theo tile.

### 4.3. Sentence fill

- Key figure fills base bars.
- Sentence slots override selected bars.
- 70/30 policy (nếu chốt):

```text
sentence_bars = round(0.7 * body_bars)
key_bars = body_bars - sentence_bars
```

Không dùng rule này nếu chưa có test rõ.

### 4.4. Promotion

- `KeyFigureSpec` registry/version gate.
- Flag default off.
- Production digest.
- Không cho Studio tự ghi repo; export + commit.

---

## 5. Những gì chưa làm

- Không có 70/30 hiện tại.
- Không có key figure tùy ý production.
- New-pattern `rhythmTemplate` hiện preview/export-only.
- Publish SQLite không đưa spec vào composer runtime.
- Promote pattern/sentence vẫn là code change + flag.

---

## 6. Thứ tự thực hiện

| Sprint | Việc | Kết quả |
|---|---|---|
| A1 | `suite_schottish_2_4` + flag + gate | Pattern 2/4 chạy production |
| A2 | Tests/digest/matrix/docs | Flag off an toàn, flag on đúng |
| B1 | `KeyFigureSpec` + rhythm materializer | Key figure từ 1 bar |
| B2 | Sentence fill + 70/30 rule nếu chốt | Pattern + sentences linh hoạt |
| B3 | Promote/registry/version | Composer dùng ổn định |

MVP nên làm **A1 + A2** trước.

---

## 7. Cần chốt

1. Làm **Bước A** với `VILLA_ARPEGGIO` trước?
2. 70/30 có bắt buộc không?
3. Key figure Bước B lấy đúng bar nào của Scottish?
4. Pattern mới chỉ chạy qua **flag** hay cần auto-selected mặc định?

Khuyến nghị:

- A trước;
- 70/30 để sau khi có key figure tùy ý;
- B chọn bar 2 hoặc bar 3 của Scottish;
- flag default off.
