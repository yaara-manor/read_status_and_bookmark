import { expect, test as setup } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"

const authFile = "playwright/.auth/user.json"

setup("authenticate", async ({ page }) => {
  await page.goto("/login")
  await page.getByTestId("email-input").fill(firstSuperuser)
  await page.getByTestId("password-input").fill(firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  await expect
    .poll(
      async () => {
        const response = await page.request.get(
          `${process.env.VITE_API_URL}/api/v1/events`,
          { headers: { Authorization: `Bearer ${token}` } },
        )
        const body = await response.json()
        return body.data.some(
          (event: { name: string }) => event.name === "Opening Night",
        )
      },
      { timeout: 20_000 },
    )
    .toBe(true)
  await page.context().storageState({ path: authFile })
})
