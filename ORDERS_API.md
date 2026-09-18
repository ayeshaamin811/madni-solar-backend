# Orders API — frontend integration guide

Backend for the **Place Order** button on `/checkout`.

This is a **form-submission API, not a payment API**. There is no payment gateway.
An order is a *request to buy*; the sales team confirms it by phone — exactly like
`/api/quotes/`. Nothing is charged, and the customer-facing copy must say so.

Base URL is whatever `src/api/client.js` already points at (`/api` prefix).

---

## Endpoints

| Method | Path | Auth | Throttle | Purpose |
|---|---|---|---|---|
| `POST` | `/api/orders/` | none | 5 / hour / IP | Place an order |
| `GET` | `/api/orders/settings/` | none | default anon | Flat shipping + currency |

---

## `POST /api/orders/`

`Content-Type: application/json`. No file upload.

### Request body

Billing field names are **camelCase** and map 1:1 to the `form` state in
`CheckoutPage.jsx`, so the form object can be spread in as-is.

| Field | Type | Required | Rules |
|---|---|---|---|
| `firstName` | string | yes | min 2 chars |
| `lastName` | string | yes | min 2 chars |
| `address` | string | yes | min 5 chars |
| `apartment` | string | no | |
| `city` | string | yes | min 2 chars |
| `state` | string | no | must be one of the 7 values below if sent |
| `postCode` | string | yes | **string, not a number** — leading zeros matter |
| `phone` | string | yes | min 7 chars |
| `email` | string | yes | valid email (required here, unlike `/api/quotes/`) |
| `businessName` | string | no | |
| `orderNotes` | string | no | free text |
| `agreedToTerms` | boolean | yes | must be `true` |
| `items` | array | yes | must be non-empty |
| `subtotal` | number | yes | cross-check, see *Price verification* |
| `shipping` | number | yes | cross-check |
| `total` | number | yes | cross-check |

**Country is not a field.** The UI shows "Pakistan" as static text; the backend
stores it as a constant.

`state` allowed values:

```
Punjab
Sindh
Khyber Pakhtunkhwa
Balochistan
Azad Kashmir
Gilgit-Baltistan
Islamabad Capital Territory
```

### `items[]`

Exactly what `CartContext` stores per line, plus the computed `lineTotal`:

```json
{
  "name": "Huawei SUN2000 5KTL Inverter",
  "slug": "huawei-sun2000-5ktl-inverter",
  "price": 185000,
  "quantity": 2,
  "lineTotal": 370000
}
```

Only **`slug`** and **`quantity`** are load-bearing. `name`, `price` and `lineTotal`
are accepted so the cart line can be posted verbatim, but the stored values come
from the catalogue, not from the browser.

Do **not** send the cart's `image` — it is a bundled frontend asset URL. The
backend resolves the real product photo from the catalogue when it needs one.

### Full example

```json
{
  "firstName": "Ali",
  "lastName": "Raza",
  "address": "House 12, Street 5, Model Town",
  "apartment": "Flat 3B",
  "city": "Lahore",
  "state": "Punjab",
  "postCode": "05400",
  "phone": "+92 300 1234567",
  "email": "ali@example.com",
  "businessName": "Raza Traders",
  "orderNotes": "Please call before delivery.",
  "agreedToTerms": true,
  "items": [
    {
      "name": "Yingli Solar 550W Mono Panel",
      "slug": "yingli-solar-550w-mono-panel",
      "price": 18500,
      "quantity": 2,
      "lineTotal": 37000
    }
  ],
  "subtotal": 37000,
  "shipping": 2000,
  "total": 39000
}
```

### Success — `201 Created`

```json
{
  "id": 12,
  "orderNumber": "MS-2026-0012",
  "total": 39000.0,
  "message": "Thank you! Your order has been received. Our team will contact you shortly to confirm."
}
```

`orderNumber` is generated server-side (`MS-<year>-<zero-padded id>`). Show it on
the success screen in place of the "demo checkout" wording — the customer quotes
it on the phone.

---

## Price verification — what can 400 on you

Prices and totals come from the browser, where they can be edited, so the backend
**does not trust them**. On every submit it:

1. Looks each `slug` up across all four catalogues (solar panels, inverters,
   batteries, accessories — slugs are globally unique by design).
2. Recomputes each `lineTotal` from the **catalogue** price.
3. Recomputes `subtotal` and `total` using the server's flat shipping rate.
4. Compares the recomputed `total` against the submitted `total`.

Two failures the checkout page has to handle:

**Catalogue price moved** → `400`

```json
{ "non_field_errors": ["Prices have changed since you added these items. Please refresh your basket."] }
```

**Stale basket** — the cart persists in `localStorage` under `madniSolarCart`
indefinitely, so any catalogue edit eventually strands someone on a slug that no
longer exists → `400`

```json
{ "items": ["These items are no longer available: old-product-slug. Please remove them from your basket."] }
```

Both are worth surfacing prominently, since the fix is "go back to the basket",
not "correct a field".

---

## Error responses

Same shape as `/api/contact/`, `/api/calculator/` and `/api/quotes/`, so a
`parseQuoteError`-style parser keeps working.

| Status | Body | Meaning |
|---|---|---|
| `400` | `{"fieldName": ["message"], ...}` | Field errors, keyed by the camelCase request field |
| `400` | `{"items": ["..."]}` | Basket-level problem |
| `400` | `{"non_field_errors": ["..."]}` | Cross-field problem (price mismatch) |
| `429` | `{"detail": "Request was throttled..."}` | 5 orders/hour per IP |
| `5xx` | — | Generic failure |

Example field errors:

```json
{
  "firstName": ["Please enter your first name."],
  "postCode": ["Please enter your postcode / ZIP."],
  "agreedToTerms": ["Please accept the terms and conditions to place your order."],
  "state": ["\"Rajasthan\" is not a valid choice."]
}
```

---

## `GET /api/orders/settings/`

```json
{ "flatShipping": 2000, "currency": "PKR" }
```

The flat rate now lives in Django settings (`ORDER_FLAT_SHIPPING`, overridable via
the `ORDER_FLAT_SHIPPING` env var). Fetch it on checkout mount instead of
hardcoding `2000`, so the number has one home. If you keep the hardcoded value,
it must stay in sync — the backend recomputes `total` with its own constant and
will 400 on a mismatch.

---

## Frontend wiring

### 1. `src/api/orders.js` (new)

Mirrors `src/api/quotes.js`:

```js
import client from "./client";

export const placeOrder = (payload) =>
  client.post("/orders/", payload).then((res) => res.data);

export const getOrderSettings = () =>
  client.get("/orders/settings/").then((res) => res.data);

export const parseOrderError = (error) => {
  const data = error?.response?.data;
  const status = error?.response?.status;

  if (status === 429) {
    return { formError: "Too many orders from this device. Please try again later.", errors: {} };
  }
  if (status === 400 && data && typeof data === "object") {
    const { non_field_errors: nonField, ...fields } = data;
    return {
      formError: nonField?.[0] || "",
      errors: Object.fromEntries(
        Object.entries(fields).map(([k, v]) => [k, Array.isArray(v) ? v[0] : String(v)])
      ),
    };
  }
  return { formError: "Something went wrong. Please try again.", errors: {} };
};
```

### 2. `CartContext.jsx` — add `clearBasket`

The provider currently exposes only `addToBasket` / `removeFromBasket`, so there
is **no way to empty the basket**. Without this the customer's items sit in
`localStorage` forever after a successful order.

```js
const clearBasket = () => setCartItems([]);

// ...and add it to the provider value:
<CartContext.Provider value={{ cartItems, addToBasket, removeFromBasket, clearBasket }}>
```

### 3. `CheckoutPage.jsx`

- Give the terms checkbox state — it is currently uncontrolled and unvalidated —
  and send it as `agreedToTerms`.
- Add `status` / `errors` / `formError` state the same way `ContactPage.jsx` does
  (`idle → sending → success | error`), and disable **Place Order** while sending.
- Replace the `setSubmitted(true)` placeholder with a real call.
- Call `clearBasket()` **only after** a `201`.
- Show the returned `orderNumber` on the success screen instead of the
  "demo checkout, no payment has been processed" wording.

```js
const shipping = 2000; // or from getOrderSettings()
const subtotal = cartItems.reduce((sum, i) => sum + i.price * i.quantity, 0);

const handleSubmit = async (e) => {
  e.preventDefault();
  setStatus("sending");
  setErrors({});
  setFormError("");

  try {
    const data = await placeOrder({
      ...form,
      agreedToTerms,
      items: cartItems.map(({ name, slug, price, quantity }) => ({
        name,
        slug,
        price,
        quantity,
        lineTotal: price * quantity,
      })),
      subtotal,
      shipping,
      total: subtotal + shipping,
    });

    setOrderNumber(data.orderNumber);
    clearBasket();
    setStatus("success");
  } catch (error) {
    const { formError, errors } = parseOrderError(error);
    setFormError(formError);
    setErrors(errors);
    setStatus("error");
  }
};
```

Note the `cartItems.map` — it deliberately drops `image` and any other cart-only
fields.

---

## Admin (for the sales team)

Orders land in Django admin under **Orders**, with the line items as an inline.

- List: order number, customer, phone, total, status, date
- Filter: status, date, province
- Search: order number, phone, email
- `status` is the only editable field (`pending → confirmed → completed`, plus
  `cancelled`) and is editable straight from the list view. The frontend never
  sets or reads it.

Customer-submitted data is read-only once saved — it is a record of what arrived.

---

## Emails

Both are sent in a background thread, so a slow SMTP round trip never delays the
`201`. A mail failure is logged and never fails the order.

- **Team notification** → `ORDER_NOTIFY_EMAILS` (env var, comma-separated):
  full billing block, item table, subtotal / shipping / total, order notes.
- **Customer confirmation** → the `email` on the order: order number, item table,
  totals, delivery address, and an explicit line that this is an order request
  and no payment has been taken.

---

## New environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ORDER_NOTIFY_EMAILS` | `info@madnisolar.com` | Comma-separated team recipients |
| `ORDER_FLAT_SHIPPING` | `2000` | Flat delivery charge |
| `ORDER_CURRENCY` | `PKR` | Display currency label |

None are required — all have defaults — so the deploy works without setting them.
