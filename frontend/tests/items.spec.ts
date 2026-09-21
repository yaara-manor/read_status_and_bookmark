import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import {
  randomEmail,
  randomItemDescription,
  randomItemTitle,
  randomPassword,
} from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"

test("Items page is accessible and shows correct title", async ({ page }) => {
  await page.goto("/items")
  await expect(page.getByRole("heading", { name: "Items" })).toBeVisible()
  await expect(page.getByText("Create and manage your items")).toBeVisible()
})

test("Add Item button is visible", async ({ page }) => {
  await page.goto("/items")
  await expect(page.getByRole("button", { name: "Add Item" })).toBeVisible()
})

test("unknown item redirects to items with not found", async ({ page }) => {
  await page.goto(`/items/${crypto.randomUUID()}`)
  await expect(page.getByRole("heading", { name: "Items" })).toBeVisible()
  await expect(page.getByText("Item not found")).toBeVisible()
})

test("invalid item id redirects to items with not found", async ({ page }) => {
  await page.goto("/items/not-a-uuid")
  await expect(page.getByRole("heading", { name: "Items" })).toBeVisible()
  await expect(page.getByText("Item not found")).toBeVisible()
})

test.describe("Items management", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string
  const password = randomPassword()

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email, password)
    await page.goto("/items")
  })

  test("Create a new item successfully", async ({ page }) => {
    const title = randomItemTitle()
    const description = randomItemDescription()

    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill(title)
    await page.getByLabel("Description").fill(description)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Item created successfully")).toBeVisible()
    await expect(page.getByText(title)).toBeVisible()
  })

  test("Create item with only required fields", async ({ page }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill(title)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Item created successfully")).toBeVisible()
    await expect(page.getByText(title)).toBeVisible()
  })

  test("Cancel item creation", async ({ page }) => {
    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill("Test Item")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("Title is required", async ({ page }) => {
    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill("")
    await page.getByLabel("Title").blur()

    await expect(page.getByText("Title is required")).toBeVisible()
  })

  test("clicking a row opens the item page", async ({ page }) => {
    const title = randomItemTitle()
    const description = randomItemDescription()

    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill(title)
    await page.getByLabel("Description").fill(description)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Item created successfully")).toBeVisible()

    const itemRow = page.getByRole("row").filter({ hasText: title })
    const id = (await itemRow.locator(".font-mono").innerText()).trim()
    await itemRow.getByText(title).click()

    await expect(page).toHaveURL(new RegExp(`/items/${id}$`))
    await expect(page.getByRole("heading", { name: title })).toBeVisible()
    await expect(page.getByText(description)).toBeVisible()
    await expect(page.getByText(id, { exact: true })).toBeVisible()
    await expect(
      page.getByRole("definition").filter({ hasText: "Test User" }),
    ).toBeVisible()
  })

  test("Copy ID does not open the item page", async ({ page }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill(title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Item created successfully")).toBeVisible()

    const itemRow = page.getByRole("row").filter({ hasText: title })
    await itemRow.getByRole("button", { name: "Copy ID" }).click()

    await expect(page).toHaveURL(/\/items$/)
    await expect(page.getByRole("heading", { name: "Items" })).toBeVisible()
  })

  test("row actions menu does not open the item page", async ({ page }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill(title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Item created successfully")).toBeVisible()

    const itemRow = page.getByRole("row").filter({ hasText: title })
    await itemRow.getByRole("button").last().click()

    await expect(page.getByRole("menuitem", { name: "Edit Item" })).toBeVisible()
    await expect(page).toHaveURL(/\/items$/)
  })

  test.describe("Edit and Delete", () => {
    let itemTitle: string

    test.beforeEach(async ({ page }) => {
      itemTitle = randomItemTitle()

      await page.getByRole("button", { name: "Add Item" }).click()
      await page.getByLabel("Title").fill(itemTitle)
      await page.getByRole("button", { name: "Save" }).click()
      await expect(page.getByText("Item created successfully")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()
    })

    test("Edit an item successfully", async ({ page }) => {
      const itemRow = page.getByRole("row").filter({ hasText: itemTitle })
      await itemRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Edit Item" }).click()

      const updatedTitle = randomItemTitle()
      await page.getByLabel("Title").fill(updatedTitle)
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Item updated successfully")).toBeVisible()
      await expect(page.getByText(updatedTitle)).toBeVisible()
    })

    test("Delete an item successfully", async ({ page }) => {
      const itemRow = page.getByRole("row").filter({ hasText: itemTitle })
      await itemRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Delete Item" }).click()

      await page.getByRole("button", { name: "Delete" }).click()

      await expect(
        page.getByText("The item was deleted successfully"),
      ).toBeVisible()
      await expect(page.getByText(itemTitle)).not.toBeVisible()
    })

    test("Edit an item from the item page", async ({ page }) => {
      const itemRow = page.getByRole("row").filter({ hasText: itemTitle })
      const id = (await itemRow.locator(".font-mono").innerText()).trim()
      await itemRow.getByText(itemTitle).click()
      await expect(page).toHaveURL(new RegExp(`/items/${id}$`))

      await page.locator("main .mx-auto").getByRole("button").click()
      await page.getByRole("menuitem", { name: "Edit Item" }).click()

      const updatedTitle = randomItemTitle()
      await page.getByLabel("Title").fill(updatedTitle)
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Item updated successfully")).toBeVisible()
      await expect(page).toHaveURL(new RegExp(`/items/${id}$`))
      await expect(
        page.getByRole("heading", { name: updatedTitle }),
      ).toBeVisible()
    })

    test("Delete an item from the item page", async ({ page }) => {
      const itemRow = page.getByRole("row").filter({ hasText: itemTitle })
      await itemRow.getByText(itemTitle).click()

      await page.locator("main .mx-auto").getByRole("button").click()
      await page.getByRole("menuitem", { name: "Delete Item" }).click()
      await page.getByRole("button", { name: "Delete" }).click()

      await expect(
        page.getByText("The item was deleted successfully"),
      ).toBeVisible()
      await expect(page.getByRole("heading", { name: "Items" })).toBeVisible()
      await expect(page.getByText(itemTitle)).not.toBeVisible()
      await expect(page.getByText("Item not found")).not.toBeVisible()
    })
  })
})

test.describe("Shared items", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("other user sees item and creator but not actions", async ({ page }) => {
    const password = randomPassword()
    const emailA = randomEmail()
    const emailB = randomEmail()
    await createUser({ email: emailA, password })
    await createUser({ email: emailB, password })

    await logInUser(page, emailA, password)
    await page.goto("/items")
    const title = randomItemTitle()
    await page.getByRole("button", { name: "Add Item" }).click()
    await page.getByLabel("Title").fill(title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Item created successfully")).toBeVisible()

    await logOutUser(page)
    await logInUser(page, emailB, password)
    await page.goto("/items")

    const itemRow = page.getByRole("row").filter({ hasText: title })
    await expect(itemRow).toBeVisible()
    await expect(itemRow.getByText("Test User")).toBeVisible()
    await expect(itemRow.getByRole("button")).toHaveCount(1)

    await itemRow.getByText(title).click()
    await expect(page.getByRole("heading", { name: title })).toBeVisible()
    await expect(
      page.getByRole("definition").filter({ hasText: "Test User" }),
    ).toBeVisible()
    await expect(page.locator("main .mx-auto").getByRole("button")).toHaveCount(
      0,
    )
  })
})

test.describe("Items empty state", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Shows empty state message when no items exist", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()
    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto("/items")

    await expect(page.getByRole("heading", { name: "Items" })).toBeVisible()
  })
})
