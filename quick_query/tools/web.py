try:
    import tls_client
except ImportError
    import sys
    print("Need to install tls-client (pip install tls-client) to use the web tool.", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:
    print("Need to install BeautifulSoup (pip install beautifulsoup4) to use the web tool.", file=sys.stderr)
    sys.exit(1)

import re 

def fetch_page(
    url: str,
    clean: bool = True
) -> str:
    """
    Retrieve the HTML content of the given URL using a TLS‑Client session.

    Parameters:
        url : str - The full URL of the webpage to download.
        clean : bool - If False, returns raw HTML.  If True, returns only the content.

    Returns:
        str
            The raw text (HTML) of the response. If an error occurs, an empty string is returned.
    """
    try:
        session = tls_client.Session(client_identifier="chrome_108")
        response = session.get(url)
        if clean:
            return compact_html(response.text)
        return response.text
    except Exception:
        raise
        return ""

def compact_html(html: str) -> str: 
    """ 
    Convert an HTML page into a concise, structured plain‑text representation. 
    """ 

    # ------------------------------------------------- 
    # 1️⃣ Parse the document 
    # ------------------------------------------------- 
    soup = BeautifulSoup(html, "lxml")          # lxml is faster; fallback to html.parser if not installed 

    # ------------------------------------------------- 
    # 2️⃣ Remove noise: scripts, styles, comments, hidden elements 
    # ------------------------------------------------- 
    for element in soup(["script", "style", "noscript", "template"]): 
        element.decompose() 

    # Remove HTML comments 
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)): 
        comment.extract() 

    # Optionally drop elements that are hidden via CSS (simple heuristic) 
    for el in soup.select("[style*='display:none'], [hidden]"): 
        el.decompose() 

    # ------------------------------------------------- 
    # 3️⃣ Helper to clean whitespace 
    # ------------------------------------------------- 
    def clean(text: str) -> str: 
        """Collapse whitespace and strip leading/trailing spaces.""" 
        return re.sub(r"\s+", " ", text).strip() 

    # ------------------------------------------------- 
    # 4️⃣ Walk the DOM in document order & emit structured text 
    # ------------------------------------------------- 
    lines = [] 

    for el in soup.body.descendants:   # start from <body> if it exists; otherwise whole doc 
        if isinstance(el, str): 
            continue                     # skip raw strings – we handle them via their parent tags 

        # --- Headings --------------------------------------------------------- 
        if el.name and re.fullmatch(r"h[1-6]", el.name): 
            level = int(el.name[1]) 
            heading = clean(el.get_text(separator=" ")) 
            lines.append("#" * level + " " + heading) 

        # --- Paragraphs ------------------------------------------------------- 
        elif el.name == "p": 
            txt = clean(el.get_text(separator=" ")) 
            if txt: 
                lines.append(txt) 

        # --- Lists ------------------------------------------------------------ 
        elif el.name in ("ul", "ol"): 
            # We’ll handle individual <li> elements below 
            continue 

        elif el.name == "li": 
            prefix = "-" if el.parent.name == "ul" else "1." 
            txt = clean(el.get_text(separator=" ")) 
            lines.append(f"{prefix} {txt}") 

        # --- Tables ------------------------------------------------------------ 
        elif el.name == "table": 
            # Simple linearised view: each row becomes a pipe‑separated line. 
            for tr in el.find_all("tr"): 
                cells = [clean(td.get_text()) for td in tr.find_all(["th", "td"])] 
                if cells: 
                    lines.append("| " + " | ".join(cells) + " |") 

        # --- Links ------------------------------------------------------------- 
        elif el.name == "a": 
            href = el.get("href") or "" 
            link_text = clean(el.get_text()) 
            if href and link_text: 
                lines.append(f"[{link_text}]({href})") 
            elif href: 
                lines.append(f"{href}") 

        # --- Images (alt text) ------------------------------------------------- 
        elif el.name == "img": 
            alt = el.get("alt") 
            src = el.get("src") 
            if alt and src: 
                lines.append(f"![{alt}]({src})") 
            elif alt: 
                lines.append(f"[Image: {alt}]") 
            elif src: 
                lines.append(f"[Image: {src}]") 

        # --- Anything else that carries visible text (blockquote, pre, etc.) ----- 
        elif el.name in ("blockquote", "pre", "code"): 
            txt = clean(el.get_text(separator="\n")) 
            if txt: 
                lines.append(txt) 

    # ------------------------------------------------- 
    # 5️⃣ Final normalisation: collapse multiple newlines 
    # ------------------------------------------------- 
    compact = "\n\n".join(filter(None, (line.strip() for line in lines))) 
    return compact
