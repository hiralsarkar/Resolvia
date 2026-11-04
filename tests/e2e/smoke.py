"""
Clicks through the running app the way a visitor would and fails on any
error box. Screenshots go to e2e-shots/. Usage: python tests/e2e/smoke.py URL
"""
import os
import sys
from playwright.sync_api import sync_playwright

FRESH = sys.argv[2] if len(sys.argv) > 2 else "BRK02998"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
OUT = "e2e-shots"
os.makedirs(OUT, exist_ok=True)
problems = []


def settle(page):
    page.wait_for_timeout(800)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=120000)
    page.wait_for_timeout(1500)


def check(page, name):
    settle(page)
    page.screenshot(path=f"{OUT}/{name}.png", full_page=True)
    errs = page.locator('[data-testid="stException"], [data-testid="stAlertContentError"]')
    for i in range(errs.count()):
        problems.append(f"{name}: {errs.nth(i).inner_text()[:300]}")
    body = page.inner_text("body")
    for bad in ("Failed to fetch dynamically imported module", "Traceback", "StreamlitAPIException"):
        if bad in body:
            problems.append(f"{name}: page contains '{bad}'")
    print(f"checked {name}", flush=True)


def nav(page, label):
    page.locator('section[data-testid="stSidebar"] label').filter(has_text=label).first.click()


def click(page, text):
    page.get_by_role("button", name=text).first.click()


with sync_playwright() as p:
    page = p.chromium.launch().new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: m.type == "error" and "dynamically imported" in m.text and problems.append(f"console: {m.text[:200]}"))
    page.goto(URL, timeout=120000)
    page.wait_for_selector('section[data-testid="stSidebar"]', timeout=180000)
    check(page, "01-agent-architecture")

    click(page, "Start Reviewing Exceptions")
    check(page, "02-break-queue-from-landing")

    for i, label in enumerate(["Home", "Break Queue", "Case Workspace", "Resolution", "Manual Guide",
                               "Audit Trail", "Manager Overview"], start=3):
        nav(page, label)
        check(page, f"{i:02d}-{label.lower().replace(' ', '-')}")

    nav(page, "Home"); settle(page)
    click(page, "Open break queue")
    check(page, "10-home-open-break-queue")
    if "Break Queue" not in page.inner_text("h1, h2, h3, body"):
        problems.append("Home 'Open break queue' did not open the Break Queue")

    nav(page, "Home"); settle(page)
    page.get_by_role("button", name="Open", exact=True).first.click()
    check(page, "11-case-from-needs-attention")

    # a fresh break, worked end to end: search, select the row, run the agents
    nav(page, "Break Queue"); settle(page)
    page.locator('[data-testid="stMain"] input[aria-label="Search"], section.main input[aria-label="Search"]').first.fill(FRESH); page.keyboard.press("Enter"); settle(page)
    grid = page.locator('[data-testid="stDataFrame"]').first
    box = grid.bounding_box()
    page.mouse.click(box["x"] + 18, box["y"] + 52)  # row selector of the first row
    check(page, "12-queue-selected")
    for name in ("Open case", "Open the case", "Work this break", "Case workspace"):
        btn = page.get_by_role("button", name=name)
        if btn.count():
            btn.last.click(); break
    else:
        nav(page, "Case Workspace")
    check(page, "13-fresh-case")
    if page.get_by_role("button", name="Start case review").count():
        page.get_by_role("button", name="Start case review").first.click()
        page.wait_for_timeout(5000)
        check(page, "14-fresh-case-reviewed")
    else:
        problems.append("fresh case: no 'Start case review' button")
    nav(page, "Resolution")
    check(page, "15-fresh-resolution")
    print("buttons on resolution:", [b.inner_text() for b in page.get_by_role("button").all()][:30], flush=True)

    page.context.browser.close()

print("\n".join(problems) or "no problems found")
sys.exit(1 if problems else 0)
