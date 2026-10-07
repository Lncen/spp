const { chromium } = require("@playwright/test")

const outDir =
  "C:\\Users\\ini\\.codex\\visualizations\\2026\\10\\07\\01a115dc-e3bd-72c1-8725-307154d86884"

const combos = Array.from({ length: 6 }, (_, i) => ({
  id: `combo-${i + 1}`,
  name: `示例组合 ${i + 1}`,
  remark: i % 2 === 0 ? "抖音链接，固定数量" : "无备注内容",
  item_count: (i % 3) + 1,
  created_at: "2026-10-07T10:00:00+08:00",
  updated_at: "2026-10-07T10:00:00+08:00",
}))

async function main() {
  const browser = await chromium.launch({ channel: "chrome", headless: true })
  for (const [width, height] of [
    [1920, 1000],
    [1600, 900],
    [1440, 900],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } })
    await page.route("**/api/v1/product-combos/me**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: combos, count: combos.length }),
      }),
    )
    await page.route("**/api/v1/product-favorites/me**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], count: 0 }),
      }),
    )
    await page.goto("http://localhost:5200/", { waitUntil: "networkidle" })
    await page.waitForTimeout(1200)
    const cardBox = await page.locator("div.grid > div").first().boundingBox()
    const buttons = await page
      .locator("div.grid > div")
      .first()
      .locator("button")
      .evaluateAll((nodes) =>
        nodes.map((node) => Math.round(node.getBoundingClientRect().width)),
      )
    const actionRow = await page
      .locator("div.grid > div")
      .first()
      .locator("div.flex.flex-wrap")
      .first()
      .boundingBox()
    console.log(
      JSON.stringify({
        width,
        cardWidth: Math.round(cardBox.width),
        buttons,
        buttonsTotal: buttons.reduce((sum, w) => sum + w, 0),
        actionRowWidth: Math.round(actionRow.width),
      }),
    )
    await page.screenshot({
      path: `${outDir}\\combos-cards-${width}${process.env.SUFFIX ?? ""}.png`,
    })
    await page.close()
  }
  await browser.close()
}

main().catch((error) => {
  console.error("FAILED", error)
  process.exit(1)
})
