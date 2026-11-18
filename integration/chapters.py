"""Tolerant TXT chapter planning with unchanged source coordinates."""
import re
import unicodedata
from collections import Counter,defaultdict
from dataclasses import dataclass
from yueji_plot.models import Boundary,Chapter,Paragraph
from yueji_plot.ingestion import stable_id

NUM=r'[零〇一二三四五六七八九十百千万两兩\d]+'
NUMBERED=re.compile(rf'^第\s*({NUM})\s*([章回节節卷部集])(?P<tail>.*)$')
DECORATIONS='【】[]〔〕〖〗《》<>「」『』*#=─━-'
NOISE=re.compile(r'^(?:目\s*录|正文|返回目录|返回书页|[上下一]+页|上一章|下一章|点击下一页|本章未完.{0,30}|下载地址.{0,100}|TXT下载.{0,100})$|^(?:https?://|www\.)\S+$|(?:更多.{0,5}(?:好书|小说)|请.{0,4}(?:收藏|记住).{0,6}(?:本站|网址|域名))',re.I)

@dataclass
class Plan:
    boundaries:list
    excluded:set
    warnings:list
    synthetic:bool=False


def clean(line):
    return unicodedata.normalize('NFKC',line).replace('\ufeff','').replace('\u200b','').strip().strip(DECORATIONS).strip()


def candidates_for(lines):
    explicit=[];fallback=[];volumes=set()
    previous={};last=''
    for i,line in enumerate(lines,1):
        previous[i]=last
        if line.strip():last=line.strip()
    for i,line in enumerate(lines,1):
        s=clean(line)
        if not s or len(s)>200:continue
        s=re.sub(r'^正文\s*','',s)
        m=NUMBERED.fullmatch(s)
        if m:
            tail=m['tail'];unit=m[2]
            if unit in '卷部集':
                # Narrative like “第一卷结束了...” is body, not a volume header.
                if (not tail or tail[0].isspace() or (len(s)<=35 and not re.search(r'[，。]|^(?:结束|的|是|中|里)',tail))):volumes.add(i)
                continue
            if unit in '节節' and (len(s)>60 or ('。' in tail) or (tail and not tail[0].isspace() and '，' in tail)):continue
            if re.match(r'^(?:中(?:的|既|提)|里(?:的|提)|曾经|已经|写道|讲述)',tail):continue
            if tail and not tail[0].isspace() and tail.startswith(('的','中','里','内','所','曾')) and '。' in tail:continue
            item=(Boundary(line=i,title=line.strip().replace("\ufeff","").replace("\u200b","").strip(DECORATIONS).strip()),unit,len(line)-len(line.lstrip()),not tail.strip())
            explicit.append(item)
        elif re.fullmatch(rf'{NUM}[、.．]?(?:\s+\S.{{0,90}})?',s) or re.fullmatch(r'\d{1,5}[.、]\s*\S.{0,90}',s) or re.match(r'^chapter\s+\d+\b',s,re.I):
            fallback.append((Boundary(line=i,title=line.strip().replace("\ufeff","").replace("\u200b","").strip(DECORATIONS).strip()),'number',len(line)-len(line.lstrip()),False))
    # Prefer real chapter-level headings to internal numbered lists/sections.
    chosen=[v for v in explicit if v[1] in '章回']
    if not chosen:chosen=explicit or fallback
    if not chosen and volumes:chosen=[(Boundary(line=i,title=clean(lines[i-1])),'volume',0,False) for i in sorted(volumes)];volumes=set()
    ignored=set(volumes)
    groups=defaultdict(list)
    for v in chosen:
        if v[3]:groups[v[2]].append(v)
    body_indent=Counter(len(s)-len(s.lstrip()) for s in lines if len(s.strip())>35 and not NUMBERED.match(clean(s))).most_common(1)
    def breaks_sentence(group):
        broken=0
        for boundary,*_ in group:
            prior=previous[boundary.line]
            if len(prior)>12 and prior[-1] not in '。！？!?….””\"\'：:；;':broken+=1
        return broken/max(1,len(group))
    if body_indent and len(groups)>1:
        primary=groups.get(body_indent[0][0],[])
        if len(primary)>=3 and breaks_sentence(primary)<.25:
            for indent,group in groups.items():
                if indent!=body_indent[0][0] and len(group)>=3 and breaks_sentence(group)>=.35:
                    ignored.update(v[0].line for v in group)
    boundaries=[v[0] for v in chosen if v[0].line not in ignored]
    return boundaries,ignored


def plan_chapters(text,boundaries=None):
    lines=text.splitlines(keepends=True)
    automatic,ignored=candidates_for(lines)
    noise={i for i,s in enumerate(lines,1) if NOISE.search(s.strip()) and len(s.strip())<=300}
    ignored |= noise
    def prune(items):
        kept=[];empty=set()
        for index,b in enumerate(items):
            end=items[index+1].line if index+1<len(items) else len(lines)+1
            if any(lines[n-1].strip() and n not in ignored for n in range(b.line+1,end)):
                kept.append(b)
            else:empty.add(b.line)
        return kept,empty
    auto,empty=prune(automatic);ignored |= empty
    selected=auto if boundaries is None else [v if isinstance(v,Boundary) else Boundary.model_validate(v) for v in boundaries]
    loc=[v.line for v in selected]
    if loc and (loc!=sorted(set(loc)) or loc[-1]>len(lines)):raise ValueError('章节起始行必须递增且位于原文内')
    selected=[v for v in selected if v.line not in ignored]
    selected,more_empty=prune(selected);ignored |= more_empty
    warnings=[]
    if empty or more_empty:warnings.append('已自动跳过没有正文的目录项或空章节标题。')
    if ignored-noise-empty-more_empty:warnings.append('已忽略疑似分页页眉、页码及卷标题，保留实际章节。')
    if noise:warnings.append('已忽略网址、翻页提示等明显非正文行。')
    synthetic=not selected or (len(selected)==1 and selected[0].line==1 and selected[0].title=='正文' and not NUMBERED.fullmatch(clean(lines[0])))
    if synthetic:
        if not any(s.strip() and i not in ignored for i,s in enumerate(lines,1)):raise ValueError('未找到可导入的正文，请检查TXT内容')
        selected=[Boundary(line=1,title='正文')]
        warnings.append('未找到可靠的章节标题，已按单章正文导入，可在预览中调整目录。')
    return Plan(selected,ignored,warnings,synthetic)


def parse_plan(text,plan):
    lines=text.splitlines(keepends=True);offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line))
    digest=stable_id(text);chapters=[]
    for index,b in enumerate(plan.boundaries):
        first=1 if index==0 else b.line
        end=plan.boundaries[index+1].line if index+1<len(plan.boundaries) else len(lines)+1
        paragraphs=[]
        for n in range(first,end):
            original=lines[n-1];value=original.strip()
            if not value or n in plan.excluded or (n==b.line and not plan.synthetic):continue
            start=offsets[n-1]+original.index(value)
            paragraphs.append(Paragraph(id=stable_id(digest,start,start+len(value)),chapter=index+1,number=len(paragraphs)+1,start=start,end=start+len(value),text=value))
        if paragraphs:chapters.append(Chapter(id=stable_id(digest,b.line),number=len(chapters)+1,title=b.title,line=b.line,paragraphs=paragraphs))
    if not chapters:raise ValueError('未找到可导入的正文，请检查TXT内容')
    return chapters


def detect_boundaries(text):return plan_chapters(text).boundaries
