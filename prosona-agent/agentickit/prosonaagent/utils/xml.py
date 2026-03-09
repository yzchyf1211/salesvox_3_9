def prettify_xml(text, indent_size: int = 2) -> str | None:
    """
    对齐XML标签的换行，统一缩进格式

    参数:
        text: 包含XML标签的文本内容
        indent_size: 缩进空格数，默认为2

    返回:
        格式化后的文本，XML标签对齐换行
    """
    if not text:
        return text

    lines = text.strip().split("\n")
    result_lines = []
    reach_xml_start_tag = False
    level = 0
    # xml下的第一个有内容的行的缩进，决定了后续行的缩进基础偏移量
    offset = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result_lines.append("")
            continue

        # 检查是否是XML标签（必须以<开头且以>结尾）
        is_xml_start_tag = (
            stripped.startswith("<")
            and not stripped.startswith("</")
            and stripped.endswith(">")
        )

        is_xml_end_tag = stripped.startswith("</") and stripped.endswith(">")

        # 下一个有内容的行，读取它的indent
        if is_xml_start_tag:
            reach_xml_start_tag = True
            result_lines.append(indent_size * level * " " + stripped)
            level += 1

        elif is_xml_end_tag:
            level -= 1
            result_lines.append(indent_size * level * " " + stripped)

        elif reach_xml_start_tag:
            reach_xml_start_tag = False
            # 添加当前行的缩进
            indent = len(line) - len(line.lstrip())
            offset = max(indent_size * level, indent)
            result_lines.append((offset - indent) * " " + line)

        else:
            indent = len(line) - len(line.lstrip())
            result_lines.append((offset - indent) * " " + line)

    return "\n".join(result_lines)
