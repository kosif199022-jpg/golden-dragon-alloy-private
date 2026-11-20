"""Production decisions distilled from caption shaping, editing and motion design."""
import re


def caption_method(request):
    text=request.casefold()
    if not re.search(r"caption|subtitle|كابشن|ترجم[ةه]|الترجمة",text):
        return []
    steps=[{"action":"Place each cue on the final edit. Split it at cut boundaries and omit speech removed by the cut.","verify":"Compare cue starts and ends with the delivered timeline; a gap in speech has no caption."}]
    if re.search(r"arabic|rtl|عرب",text):
        steps.append({"action":"Shape complete Arabic lines with a font that covers the text, preserving logical order.","verify":"Inspect an exported frame containing joined letters and a mixed number or punctuation mark."})
    if re.search(r"\bmotion\b|\bgraphics?\b|\btitles?\b|موشن|عنوان|عناوين",text):
        steps.append({"action":"Reserve the caption region before positioning titles, counters and animated graphics.","verify":"Inspect a frame where a caption and a moving graphic appear together; both must remain legible."})
    steps.append({"action":"Preview an early cue, a late cue and a silent interval against the actual picture.","verify":"Compare export duration and audio with the planned edit before delivery."})
    return steps
