"""Offline TXT decoding with BOMs, bounded detection and visible lossy repair."""
import codecs
import re

from charset_normalizer import from_bytes

SAMPLE_BYTES = 65536
CONTROLS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
HEADINGS = re.compile(r'(?m)^\s*(?:第[零〇一二三四五六七八九十百千万两\d]+[章回节卷部集]|Chapter\s+\d+)',re.I)
BOMS = ((codecs.BOM_UTF32_LE,'utf-32'),(codecs.BOM_UTF32_BE,'utf-32'),
        (codecs.BOM_UTF8,'utf-8-sig'),(codecs.BOM_UTF16_LE,'utf-16'),(codecs.BOM_UTF16_BE,'utf-16'))


def decode(raw,encoding,*,incomplete=False,repair=False):
    return codecs.getincrementaldecoder(encoding)(errors='replace' if repair else 'strict').decode(raw,final=not incomplete)


def guess(raw,default=None):
    sample=raw[:SAMPLE_BYTES]
    try:
        text=decode(sample,'utf-8-sig',incomplete=len(raw)>len(sample))
        if '\x00' not in text:return 'utf-8-sig',False
    except UnicodeError:pass
    # A complete line prevents sampling halfway through a GB18030/Big5 codepoint.
    if len(raw)>len(sample) and b'\x00' not in sample:
        end=sample.rfind(b'\n')
        if end>=len(sample)//2:sample=sample[:end+1]
    for trim in range(4):
        part=sample[:-trim] if trim else sample
        if not part:break
        matches=from_bytes(part)
        candidates=list(dict.fromkeys([m.encoding for m in matches]+['utf-8-sig','gb18030','big5']))
        ranked=[]
        for candidate in candidates:
            try:ranked.append((len(HEADINGS.findall(decode(part,candidate))),candidate))
            except UnicodeError:pass
        if ranked:
            score,candidate=max(ranked,key=lambda pair:pair[0])
            if score:return candidate,False
        match=matches.best()
        if match is not None:return match.encoding,False
    if default:return default,True
    salvage=sample.decode('utf-8',errors='replace')
    mostly_utf8=salvage.count('\ufffd')/max(1,len(salvage))<.04
    return ('utf-8-sig' if mostly_utf8 else 'gb18030'),True


def decode_txt(raw: bytes,*,incomplete=False):
    encoding=next((name for bom,name in BOMS if raw.startswith(bom)),None)
    uncertain=False
    if encoding is None:encoding,uncertain=guess(raw)
    repairs=0;used=set()
    try:
        text=decode(raw,encoding,incomplete=incomplete)
        if encoding.replace('_','-') not in ('utf-8','utf-8-sig') and not encoding.replace('_','-').startswith(('utf-16','utf-32')):
            for line in raw[:SAMPLE_BYTES].splitlines():
                if not any(b>=128 for b in line):continue
                try:utf8=decode(line,'utf-8-sig')
                except UnicodeError:continue
                if HEADINGS.search(utf8):raise UnicodeError('mixed UTF-8 chapter heading')
    except UnicodeError:
        if encoding.replace('_','-').startswith(('utf-16','utf-32')):
            text=decode(raw,encoding,incomplete=incomplete,repair=True)
            repairs=text.count('\ufffd')
        else:
            # Mixed/partially damaged files are recovered per line. Pure files
            # use the fast whole-file path above, including million-char books.
            parts=[];lines=raw.splitlines(keepends=True)
            for i,line in enumerate(lines):
                tail=incomplete and i==len(lines)-1
                selected=None
                for candidate in ('utf-8-sig',encoding):
                    try:
                        value=decode(line,candidate,incomplete=tail)
                        if '\x00' in value:continue
                        selected=candidate;break
                    except UnicodeError:pass
                if selected is None:
                    repaired=decode(line,encoding,incomplete=tail,repair=True)
                    if repaired.count('\ufffd')/max(1,len(repaired))<=.1:
                        selected=encoding;value=repaired;repairs+=value.count('\ufffd')
                    else:
                        selected,doubt=guess(line,encoding);uncertain |= doubt
                        try:value=decode(line,selected,incomplete=tail)
                        except UnicodeError:
                            value=decode(line,selected,incomplete=tail,repair=True)
                            repairs+=value.count('\ufffd')
                if any(b>=128 for b in line):used.add(codecs.lookup(selected).name.replace('utf-8-sig','utf-8'))
                parts.append(value)
            text=''.join(parts)
    text=text.replace('\r\n','\n').replace('\r','\n').replace('\ufeff','')
    text,controls=CONTROLS.subn('',text)
    mixed=len(used)>1
    label='混合编码' if mixed else codecs.lookup(encoding).name.upper().replace('_','-')
    warnings=[]
    if label not in ('UTF-8','UTF-8-SIG','ASCII'):
        warnings.append(f'已自动识别{label}并转换为可读取的文本，无需手动另存。')
    if uncertain:warnings.append('部分编码无法可靠识别，已尽量恢复正文，请在预览中检查。')
    if repairs:warnings.append(f'有{repairs}处损坏或不可识别字符已替换为“�”，其余正文已保留。')
    if controls:warnings.append(f'已清理{controls}个不可显示的控制字符。')
    return text,{'encoding':label,'encoding_repaired':bool(repairs or controls or mixed or uncertain),
                'replacement_count':repairs,'warnings':warnings}
