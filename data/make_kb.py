"""Generates the seed knowledge base. Run from repo root: python data/make_kb.py
Clear data/ first (rm -rf data/* or delete contents) so stale week-1 files don't linger."""
from pathlib import Path

DOCS = {
"policies/refund_policy.md": """
# Refund Policy

## Eligibility
- Damaged or defective items are eligible for a full refund if reported within 7 days of delivery.
- Wrong item received: full refund or free replacement, reported within 7 days of delivery.
- Unopened items in original packaging: refund within 15 days of delivery, minus shipping fees.

## Process
1. Customer reports the issue with photos of the item and packaging.
2. Support verifies the order record and delivery date.
3. Refunds above Rs. 1,000 require agent approval before processing.
4. Approved refunds are credited to the original payment method within 5-7 business days.

## Non-refundable
- Digital products after the download link has been used.
- Items damaged through customer misuse (see Warranty Policy for manufacturing defects).
- Items returned without original packaging after 15 days.
- Gift cards.

## Important
A refund is not the same as a warranty claim. Items that stop working after the refund
window should be handled under the Warranty Policy (repair or replacement), not refund.
""",

"policies/returns_exchange.md": """
# Returns and Exchanges

## Return window
Unopened items in original packaging can be returned within 15 days of delivery for a
refund (shipping fees deducted). Opened but unused items may be returned within 7 days
at support's discretion.

## Exchanges
- Size exchanges for apparel are free within 15 days if the item is unworn with tags.
- Product exchanges (different model) are treated as return + new order.
- Damaged or wrong items follow the Refund Policy instead.

## Condition requirements
Items must include all accessories, manuals, and original packaging. Missing components
may reduce the refund amount by up to 30%.

## How to start
1. Go to Orders, select the item, choose Return or Exchange.
2. Print the prepaid label (domestic orders only).
3. Drop off at any partner courier point. Refunds process 2-3 days after inspection.
""",

"policies/order_cancellation_policy.md": """
# Order Cancellation Policy

## When you can cancel
- Orders in "pending" or "processing" status can be cancelled free of charge at any time
  before they are handed to the courier.
- Once an order is "shipped" it cannot be cancelled. Options after shipping: refuse
  delivery at the door (the parcel returns to us automatically), or accept it and start
  a return under the Returns and Exchanges policy.
- Delivered orders cannot be cancelled; use the return window instead.

## Timing
Cancellations are processed immediately and refunds to the original payment method
appear within 5-7 business days. For cash-on-delivery orders, refunds are issued to
your bank account or as store credit within 3 business days.

## Express orders
Express (1-2 day) orders move to "shipped" quickly, often within 2 hours. If you need
to cancel an express order, contact support immediately.
""",

"policies/late_delivery_policy.md": """
# Late Delivery Policy

Standard domestic delivery takes 3-5 business days. If your order is late:

- Up to 3 business days past the expected date: check tracking first; courier delays
  usually resolve within a day. Contact support if tracking has not updated for 48 hours.
- More than 5 business days past the expected date: shipping fees are refunded
  automatically when you contact support.
- More than 10 business days past the expected date: in addition to the shipping
  refund, you receive store credit worth 10% of the order value.

This policy applies to domestic orders only. International delivery timelines are
estimates and cannot be compensated the same way (see International Shipping FAQ).

Late delivery compensation is separate from refunds for damaged or wrong items, which
follow the Refund Policy.
""",

"policies/warranty_policy.md": """
# Warranty Policy

## Coverage
- 12 months for electronics: headphones, coffee makers, smartwatches, and similar devices.
- 6 months for accessories: desk lamps, cables, cases.
- Warranty covers manufacturing defects: dead pixels, battery failures, charging faults,
  buttons that stop working under normal use.

## Not covered
- Physical damage, liquid damage, or wear and tear.
- Damage from unauthorized repairs or modifications.
- Items that fail after the warranty period (paid service available).

## Remedy
Warranty claims result in repair or replacement of the same or equivalent model.
Warranty claims do not result in refunds. If your item arrived damaged, that is a
Refund Policy case (7-day window), not a warranty case.

## Making a claim
Contact support with your order ID and a description or video of the fault. Approved
claims ship a replacement within 3 business days; the faulty unit is collected by
courier at no cost.
""",

"faqs/shipping_faq.md": """
# Shipping FAQ

## Timelines
- Standard domestic delivery: 3-5 business days.
- Express delivery: 1-2 business days (select cities).
- Order processing before dispatch: up to 24 hours.

## Couriers
We ship with Delhivery and BlueDart, chosen automatically by destination and service
level. You cannot select a specific courier.

## Tracking
A tracking link is emailed and sent by SMS once the courier scans your parcel. If
tracking has not updated for 48 hours, contact support.

## Fees
- Standard shipping is free on orders above Rs. 999.
- Below that, a flat Rs. 79 standard shipping fee applies.
- Express shipping is Rs. 199 flat.

## Address changes
Addresses can be changed only while the order is in "processing". Once shipped, the
courier must attempt delivery to the original address.
""",

"faqs/international_shipping.md": """
# International Shipping FAQ

## Destinations
We currently ship to UAE, Singapore, UK, USA, Canada, and Australia.

## Timelines
7-14 business days after dispatch. Customs processing can add 2-5 days and is outside
our control.

## Duties and taxes
Import duties and taxes are paid by the customer to the courier or customs, not to us.
Prices on our site do not include these charges.

## Restrictions
- Cash on delivery is not available for international orders.
- Express shipping is not available internationally.
- Lithium-battery products (smartwatches) ship to some destinations only due to
  air-transport rules.
""",

"faqs/cod_policy.md": """
# Cash on Delivery (COD)

- COD is available on domestic orders up to Rs. 10,000.
- A COD handling fee of Rs. 49 applies.
- COD is not available for international orders, gift cards, or express shipping.

## Failed deliveries
If a COD parcel is refused, it returns to us and the amount is not charged. Repeated
refusals (3 or more) may cause COD to be disabled on your account.

## Paying the courier
Couriers accept cash and UPI. Exact change is appreciated; couriers cannot process
cards on delivery.
""",

"faqs/payment_methods.md": """
# Payment Methods

## Accepted
UPI, credit and debit cards (Visa, Mastercard, RuPay, Amex), netbanking from all
major banks, and wallets (Paytm, PhonePe, Amazon Pay).

## EMI
EMI is available on orders above Rs. 3,000 with major credit cards and select debit
cards. No-cost EMI runs periodically on specific products.

## Failed payments
If money left your account but the order failed, banks auto-reverse within 3 business
days (T+3). If it has not, contact support with the UPI or bank reference number and
we will raise a trace with the payment gateway.

## Invoices
GST invoices download from Orders > Invoice. Business buyers can add a GSTIN before
payment (see Bulk and Business Orders).
""",

"faqs/password_reset.md": """
# Password Reset

## Steps
1. On the login page, tap "Forgot password".
2. Enter the email registered to your account.
3. You receive a 6-digit code by email, valid for 15 minutes.
4. Enter the code and choose a new password.

## Common problems
- Code not arriving: check spam, wait 2 minutes, then request again. Maximum 5 attempts
  before a 30-minute lock.
- Account locked after failed logins: unlocks automatically after 30 minutes.
- No access to the registered email: contact support with a government ID for manual
  verification. This takes 1-2 business days.

For suspicious activity on your account (not just a forgotten password), see
Account Security.
""",

"faqs/account_security.md": """
# Account Security

## Two-factor authentication
Enable 2FA in Profile > Security using any authenticator app. Codes are required at
every login. We recommend 2FA for accounts with saved cards.

## Suspicious activity
If you see orders you did not place or details changed without your action:
1. Change your password immediately.
2. Contact support with "Account security" in the subject.
3. We freeze the account, reverse unauthorized transactions where possible, and
   re-verify your identity.

## Locks vs resets
A locked account (too many failed logins) unlocks itself after 30 minutes — see
Password Reset. A frozen account (suspected compromise) requires support verification
and cannot be self-unlocked.
""",

"faqs/gift_cards.md": """
# Gift Cards

- Digital gift cards come in Rs. 500, 1,000, 2,000, and 5,000.
- Valid for 12 months from purchase; unused balance after expiry is not refunded.
- Redeem at checkout; the card applies before any loyalty points.
- Gift cards are non-refundable and cannot be exchanged for cash.
- You cannot buy a gift card using another gift card or with COD.
- A maximum of 3 gift cards can be combined per order.
""",

"faqs/loyalty_program.md": """
# Loyalty Program

## Tiers
- Silver: all customers.
- Gold: Rs. 50,000+ spent in the last 12 months. Priority support queue, free express
  shipping on 2 orders per month, early sale access.
- Platinum: Rs. 2,00,000+ spent. Dedicated account manager, free express shipping on
  all orders, 24-hour grievance SLA.

## Points
- Earn 1 point per Rs. 100 spent (excludes gift cards and shipping fees).
- 100 points = Rs. 50 off.
- Points expire 12 months after they are earned.
- Gold and Platinum earn at 1.5x and 2x respectively.

Tier reviews run monthly; tiers are held for 3 months after a drop in spend.
""",

"faqs/bulk_business_orders.md": """
# Bulk and Business Orders

- Orders of 10+ units of the same product qualify for bulk pricing (5-15% by volume).
- GST invoices with your GSTIN are available on all orders; add the GSTIN at checkout
  or in Profile > Business details.
- Approved business accounts can request Net-30 payment terms; approval takes 2-3
  business days and requires a GST registration.
- A dedicated account manager is assigned for accounts above Rs. 5,00,000 annual spend.
- Bulk orders may have extended dispatch times (3-5 business days).
""",

"products/headphones_manual.md": """
# AuroraSound X200 Wireless Headphones — Troubleshooting

## Error codes
- E-01 Battery fault: charge for 30 minutes, then hold power for 5 seconds.
- E-02 Bluetooth fault: hold the power button for 10 seconds until the LED flashes
  red/blue to clear the pairing table, then re-pair.
- E-03 Charging fault: try a different cable and power source; if E-03 persists the
  battery is covered by warranty.

## Basics
- Full charge takes 2 hours and gives up to 30 hours playback.
- IPX4 water resistance: splashes and sweat only; not for swimming or showers.
- Factory reset (all settings): hold power 15 seconds.

## Support
Charging or audio faults within 12 months of purchase are warranty cases (repair or
replacement) — see Warranty Policy. Physical damage is not covered.
""",

"products/coffee_maker_manual.md": """
# BrewMaster Pro Coffee Maker — Troubleshooting

## Error codes
- E-04 Descale needed: run a descaling cycle with citric acid solution (25g in 1L
  water) through the machine, then 2 rinse cycles with clean water.
- E-05 Heating element fault: unplug for 10 minutes, then retry. If E-05 returns,
  stop using the machine and contact support — this is a safety issue and is covered
  by warranty.
- E-06 Water reservoir fault: reseat the tank; check the float valve is clean.

## Maintenance
- Descale every 2 months (or when E-04 appears) in hard-water areas.
- Clean the brew basket and carafe weekly with warm soapy water.

## Support
The BrewMaster Pro carries a 12-month warranty (see Warranty Policy). Heating faults
are repaired or replaced; do not continue using a machine showing E-05.
""",

"products/desk_lamp_manual.md": """
# Lumina Desk Lamp — Troubleshooting

## LED indicators
- Blinks twice, pauses: loose bulb module. Power off, reseat the LED module until it
  clicks.
- Blinks five times: driver fault. Contact support; the driver is replaced as an
  accessory part.
- No light, no blink: check the power adapter with another device; adapters fail more
  often than lamps.

## Specs
- LED module life: 25,000 hours. Replacement modules are sold separately.
- The lamp is an accessory and carries a 6-month warranty — shorter than our 12-month
  electronics warranty.
- Do not use dimmer switches not rated for LED drivers.
""",

"products/smartwatch_manual.md": """
# PulseFit 2 Smartwatch — Troubleshooting

## Error codes
- E-07 Sync failure: force-close the companion app, toggle Bluetooth off/on, then
  re-pair. Sync fails when two phones hold the pairing.
- E-08 Heart-rate sensor fault: clean the sensor window; if the skin-contact icon
  still shows E-08, contact support.

## Battery and charging
- 7-day typical battery; 2-hour full charge.
- Charging below 10% repeatedly reduces battery life.

## Water resistance
5 ATM: swimming yes, diving and hot showers no.

## Support
The PulseFit 2 carries a 12-month warranty. Battery holding less than 60% of rated
capacity within 12 months is a warranty replacement.
""",

"internal/escalation_rules.md": """
# Escalation Rules (Internal — Support Agents Only)

## When to escalate
- Refunds above Rs. 10,000: team lead approval in addition to the standard approval queue.
- Threats of legal action, chargebacks, or regulatory complaints: escalate to the
  escalations queue immediately, do not negotiate.
- Gold or Platinum tier customers with negative sentiment: priority queue, first
  response within 2 hours.

## Approval queue
- High-risk assistant actions (refunds, cancellations) land in the approval queue with
  order context attached. Approve only after confirming the order record and policy
  eligibility in the assistant's citation.
- If the customer disputes a policy, link the public policy document; never quote
  internal thresholds (like the Rs. 10,000 rule above) to customers.

## SLAs
First response: 2 hours (priority) / 8 hours (standard). Resolution: 24 hours for
delivery issues, 48 hours for refunds after approval.
""",

"internal/known_issues.md": """
# Known Issues (Internal — Support Agents Only)

## BrewMaster Pro — E-05 heating faults, batch DEF-2026-02
A batch of BrewMaster Pro units shipped in Jan 2026 has elevated E-05 rates. For
orders with units from this batch: do not troubleshoot — immediately offer warranty
replacement with express shipping. Check the serial prefix "BM-26-" to identify the batch.

## PulseFit app — sync outage Feb 10
A companion-app outage caused temporary E-07 errors. If the customer's app is version
4.2.1 or later and E-07 persists, it is a real pairing issue; on older versions, ask
them to update the app first.

## Delhivery — tracking scan delays in North region
Tracking may show "in transit" for 48+ hours while parcels move. Do not file tracer
requests for scans younger than 72 hours.
""",
}

if __name__ == "__main__":
    base = Path(__file__).parent
    for rel, content in DOCS.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content.strip() + "\n")
    print(f"wrote {len(DOCS)} documents under data/")