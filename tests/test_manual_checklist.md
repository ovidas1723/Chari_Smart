# ChariSmart Manual Test Checklist

| TC ID | Scenario | Steps | Expected Result | Status |
|---|---|---|---|---|
| TC-01 | Admin login | Login with admin@example.com/admin123 | Admin dashboard opens | Pass |
| TC-02 | Donor registration | Register donor with area and donor type | Account created as unverified donor | Pass |
| TC-03 | Recipient registration | Register NGO/orphanage with capacity | Account created as unverified recipient | Pass |
| TC-04 | Volunteer registration | Register volunteer with area and capacity | Account created as unverified volunteer | Pass |
| TC-05 | Admin verification | Toggle verify for donor/recipient/volunteer | Verification status changes | Pass |
| TC-06 | Donation submission | Donor posts surplus food with valid pickup window | Donation status pending | Pass |
| TC-07 | Invalid pickup window | Pickup end after expiry | Validation blocks submission | Pass |
| TC-08 | Request submission | Recipient submits food need | Request status pending | Pass |
| TC-09 | Approve request | Admin approves request | Request status approved | Pass |
| TC-10 | Approve donation | Admin approves donation | Donation status approved | Pass |
| TC-11 | Auto match | Admin clicks Auto Match | Match created with score | Pass |
| TC-12 | Volunteer assignment | Admin assigns volunteer | Match status assigned | Pass |
| TC-13 | Pickup update | Volunteer marks picked up | Match/donation status picked_up | Pass |
| TC-14 | Delivery confirmation | Volunteer/recipient marks delivered | Match delivered, request fulfilled, donation delivered | Pass |
| TC-15 | Auto expiry | Donation expiry passes before delivery | Donation status expired | Pass |
| TC-16 | Approve notification | Approve a pending donation/request with SMTP configured | User receives approval email; SMS is also sent when Twilio is configured and phone is available | Pass |
| TC-17 | Reject notification | Reject a pending donation/request and enter a reason | User receives rejection email/SMS containing the reason; reason appears in dashboard | Pass |
