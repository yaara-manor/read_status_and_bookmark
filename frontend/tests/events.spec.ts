import { expect, type Page, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import {
  randomEmail,
  randomItemDescription,
  randomItemTitle,
  randomPassword,
} from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"

async function fillEvent(page: Page, name: string, description?: string) {
  const dialog = page.getByRole("dialog")
  await dialog.getByLabel("Name").fill(name)
  if (description) {
    await dialog.getByLabel("Description").fill(description)
  }
  await dialog.getByLabel("Venue").fill("Ma")
  await dialog.getByRole("option", { name: "Main Hall" }).click()
  await dialog.getByLabel("Performer").fill("Th")
  await dialog.getByRole("option", { name: "The Band" }).click()
  await dialog.getByLabel("Time").fill("2026-10-01T20:00")
  await dialog.getByLabel("Price").fill("25")
}

test("Events page is accessible and shows correct title", async ({ page }) => {
  await page.goto("/events")
  await expect(
    page.getByRole("heading", { name: "Events", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("Create and manage your events")).toBeVisible()
})

test("Add Event button is visible", async ({ page }) => {
  await page.goto("/events")
  await expect(page.getByRole("button", { name: "Add Event" })).toBeVisible()
})

test("unknown event redirects to events with not found", async ({ page }) => {
  await page.goto(`/events/${crypto.randomUUID()}`)
  await expect(
    page.getByRole("heading", { name: "Events", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("Event not found")).toBeVisible()
})

test("invalid event id redirects to events with not found", async ({
  page,
}) => {
  await page.goto("/events/not-a-uuid")
  await expect(
    page.getByRole("heading", { name: "Events", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("Event not found")).toBeVisible()
})

test.describe("Events management", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string
  const password = randomPassword()

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email, password)
    await page.goto("/events")
  })

  test("Create a new event successfully", async ({ page }) => {
    const title = randomItemTitle()
    const description = randomItemDescription()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title, description)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Event created successfully")).toBeVisible()
    await expect(page.getByText(title)).toBeVisible()
  })

  test("Create event with only required fields", async ({ page }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Event created successfully")).toBeVisible()
    await expect(page.getByText(title)).toBeVisible()
  })

  test("Cancel event creation", async ({ page }) => {
    await page.getByRole("button", { name: "Add Event" }).click()
    await page.getByRole("dialog").getByLabel("Name").fill("Test Event")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("Name is required", async ({ page }) => {
    await page.getByRole("button", { name: "Add Event" }).click()
    await page.getByRole("dialog").getByLabel("Name").fill("")
    await page.getByRole("dialog").getByLabel("Name").blur()

    await expect(page.getByText("Name is required")).toBeVisible()
  })

  test("opening an event marks it read in the table", async ({ page }) => {
    const unreadTitle = randomItemTitle()
    const readTitle = randomItemTitle()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, unreadTitle)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, readTitle)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    const unreadRow = page.getByRole("row").filter({ hasText: unreadTitle })
    const readRow = page.getByRole("row").filter({ hasText: readTitle })
    await expect(unreadRow.getByText("Unread")).toBeVisible()
    await expect(readRow.getByText("Unread")).toBeVisible()

    const id = (await readRow.locator(".font-mono").innerText()).trim()
    await readRow.getByText(readTitle).click()
    await expect(page).toHaveURL(new RegExp(`/events/${id}$`))
    await expect(page.getByRole("heading", { name: readTitle })).toBeVisible()

    await page.goto("/events")
    await expect(readRow.getByLabel("Read")).toBeVisible()
    await expect(unreadRow.getByText("Unread")).toBeVisible()
    await expect(unreadRow.getByLabel("Read")).toHaveCount(0)
  })

  test("clicking a row opens the event page", async ({ page }) => {
    const title = randomItemTitle()
    const description = randomItemDescription()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title, description)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    const eventRow = page.getByRole("row").filter({ hasText: title })
    const id = (await eventRow.locator(".font-mono").innerText()).trim()
    await eventRow.getByText(title).click()

    await expect(page).toHaveURL(new RegExp(`/events/${id}$`))
    await expect(page.getByRole("heading", { name: title })).toBeVisible()
    await expect(page.getByText(description)).toBeVisible()
    await expect(page.getByText(id, { exact: true })).toBeVisible()
    await expect(
      page.getByRole("definition").filter({ hasText: "Test User" }),
    ).toBeVisible()
  })

  test("Copy ID does not open the event page", async ({ page }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    const eventRow = page.getByRole("row").filter({ hasText: title })
    await eventRow.getByRole("button", { name: "Copy ID" }).click()

    await expect(page).toHaveURL(/\/events$/)
    await expect(
      page.getByRole("heading", { name: "Events", exact: true }),
    ).toBeVisible()
  })

  test("bookmarking an event from the table shows it on Bookmarked", async ({
    page,
  }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    const eventRow = page.getByRole("row").filter({ hasText: title })
    await eventRow.getByTestId("bookmark-toggle").click()
    await expect(page).toHaveURL(/\/events$/)
    await expect(eventRow.getByTestId("bookmark-toggle")).toHaveAttribute(
      "aria-pressed",
      "true",
    )

    await page.getByRole("link", { name: "Bookmarked" }).click()
    await expect(
      page.getByRole("heading", { name: "Bookmarked" }),
    ).toBeVisible()
    await expect(page.getByRole("row").filter({ hasText: title })).toBeVisible()
  })

  test("unbookmarking on Bookmarked removes the row immediately", async ({
    page,
  }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    const eventRow = page.getByRole("row").filter({ hasText: title })
    await eventRow.getByTestId("bookmark-toggle").click()
    await page.getByRole("link", { name: "Bookmarked" }).click()

    const bookmarkedRow = page.getByRole("row").filter({ hasText: title })
    await expect(bookmarkedRow).toBeVisible()
    await bookmarkedRow.getByTestId("bookmark-toggle").click()
    await expect(bookmarkedRow).toHaveCount(0)
    await expect(
      page.getByRole("heading", { name: "Bookmarked" }),
    ).toBeVisible()
  })

  test("bookmarking from the event page stays in sync with both lists", async ({
    page,
  }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    const eventRow = page.getByRole("row").filter({ hasText: title })
    const id = (await eventRow.locator(".font-mono").innerText()).trim()
    await eventRow.getByText(title).click()
    await expect(page).toHaveURL(new RegExp(`/events/${id}$`))
    await expect(page.getByRole("heading", { name: title })).toBeVisible()

    await page.getByTestId("bookmark-toggle").click()
    await expect(page.getByTestId("bookmark-toggle")).toHaveAttribute(
      "aria-pressed",
      "true",
    )

    await page.getByRole("link", { name: "Bookmarked" }).click()
    await expect(page.getByRole("row").filter({ hasText: title })).toBeVisible()

    await page.getByRole("link", { name: "Events" }).click()
    await expect(
      page
        .getByRole("row")
        .filter({ hasText: title })
        .getByTestId("bookmark-toggle"),
    ).toHaveAttribute("aria-pressed", "true")

    await page.goto(`/events/${id}`)
    await expect(page.getByRole("heading", { name: title })).toBeVisible()
    await page.getByTestId("bookmark-toggle").click()
    await expect(page.getByTestId("bookmark-toggle")).toHaveAttribute(
      "aria-pressed",
      "false",
    )

    await page.getByRole("link", { name: "Bookmarked" }).click()
    await expect(page.getByRole("row").filter({ hasText: title })).toHaveCount(
      0,
    )

    await page.getByRole("link", { name: "Events" }).click()
    await expect(
      page
        .getByRole("row")
        .filter({ hasText: title })
        .getByTestId("bookmark-toggle"),
    ).toHaveAttribute("aria-pressed", "false")
  })

  test("row actions menu does not open the event page", async ({ page }) => {
    const title = randomItemTitle()

    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    const eventRow = page.getByRole("row").filter({ hasText: title })
    await eventRow.getByRole("button").last().click()

    await expect(
      page.getByRole("menuitem", { name: "Edit Event" }),
    ).toBeVisible()
    await expect(page).toHaveURL(/\/events$/)
  })

  test.describe("Edit and Delete", () => {
    let eventName: string

    test.beforeEach(async ({ page }) => {
      eventName = randomItemTitle()

      await page.getByRole("button", { name: "Add Event" }).click()
      await fillEvent(page, eventName)
      await page.getByRole("button", { name: "Save" }).click()
      await expect(page.getByText("Event created successfully")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()
    })

    test("Edit an event successfully", async ({ page }) => {
      const eventRow = page.getByRole("row").filter({ hasText: eventName })
      await eventRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Edit Event" }).click()

      const updatedName = randomItemTitle()
      await page.getByRole("dialog").getByLabel("Name").fill(updatedName)
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Event updated successfully")).toBeVisible()
      await expect(page.getByText(updatedName)).toBeVisible()
    })

    test("Delete an event successfully", async ({ page }) => {
      const eventRow = page.getByRole("row").filter({ hasText: eventName })
      await eventRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Delete Event" }).click()

      await page.getByRole("button", { name: "Delete" }).click()

      await expect(
        page.getByText("The event was deleted successfully"),
      ).toBeVisible()
      await expect(page.getByText(eventName)).not.toBeVisible()
    })

    test("Edit an event from the event page", async ({ page }) => {
      const eventRow = page.getByRole("row").filter({ hasText: eventName })
      const id = (await eventRow.locator(".font-mono").innerText()).trim()
      await eventRow.getByText(eventName).click()
      await expect(page).toHaveURL(new RegExp(`/events/${id}$`))
      await expect(page.getByRole("heading", { name: eventName })).toBeVisible()

      await page.getByRole("button", { name: "Event actions" }).click()
      await page.getByRole("menuitem", { name: "Edit Event" }).click()

      const updatedName = randomItemTitle()
      await page.getByRole("dialog").getByLabel("Name").fill(updatedName)
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Event updated successfully")).toBeVisible()
      await expect(page).toHaveURL(new RegExp(`/events/${id}$`))
      await expect(
        page.getByRole("heading", { name: updatedName }),
      ).toBeVisible()
    })

    test("Delete an event from the event page", async ({ page }) => {
      const eventRow = page.getByRole("row").filter({ hasText: eventName })
      await eventRow.getByText(eventName).click()
      await expect(page.getByRole("heading", { name: eventName })).toBeVisible()

      await page.getByRole("button", { name: "Event actions" }).click()
      await page.getByRole("menuitem", { name: "Delete Event" }).click()
      await page.getByRole("button", { name: "Delete" }).click()

      await expect(
        page.getByText("The event was deleted successfully"),
      ).toBeVisible()
      await expect(
        page.getByRole("heading", { name: "Events", exact: true }),
      ).toBeVisible()
      await expect(page.getByText(eventName)).not.toBeVisible()
      await expect(page.getByText("Event not found")).not.toBeVisible()
    })
  })
})

test.describe("Shared events", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("other user sees event and creator but not actions", async ({
    page,
  }) => {
    const password = randomPassword()
    const emailA = randomEmail()
    const emailB = randomEmail()
    await createUser({ email: emailA, password })
    await createUser({ email: emailB, password })

    await logInUser(page, emailA, password)
    await page.goto("/events")
    const title = randomItemTitle()
    await page.getByRole("button", { name: "Add Event" }).click()
    await fillEvent(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Event created successfully")).toBeVisible()

    await logOutUser(page)
    await logInUser(page, emailB, password)
    await page.goto("/events")

    const eventRow = page.getByRole("row").filter({ hasText: title })
    await expect(eventRow).toBeVisible()
    await expect(eventRow.getByText("Test User")).toBeVisible()
    await expect(
      eventRow.getByRole("button", { name: "Copy ID" }),
    ).toBeVisible()
    await expect(eventRow.getByTestId("bookmark-toggle")).toBeVisible()
    await expect(
      eventRow.getByRole("button", { name: "Event actions" }),
    ).toHaveCount(0)

    await eventRow.getByText(title).click()
    await expect(page.getByRole("heading", { name: title })).toBeVisible()
    await expect(page.getByTestId("bookmark-toggle")).toBeVisible()
    await expect(
      page.getByRole("definition").filter({ hasText: "Test User" }),
    ).toBeVisible()
    await expect(
      page.getByRole("button", { name: "Event actions" }),
    ).toHaveCount(0)
  })
})

test.describe("Events empty state", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Shows the events heading", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()
    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto("/events")

    await expect(
      page.getByRole("heading", { name: "Events", exact: true }),
    ).toBeVisible()
  })
})
