# Customer Account and Lifecycle Architecture

ID: KB-PROD-0010  
Title: Customer Account and Lifecycle Architecture  
Category: Product / Customer Experience / Security  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Landing Page](KB-PROD-0002-landing-page.md), [Subscription Model](KB-PROD-0004-subscription-model.md), [AI Partnership Model](KB-PROD-0005-ai-partnership-model.md), [Mission-Based Onboarding Architecture](KB-PROD-0011-mission-based-onboarding-architecture.md)  
Related ADRs: [ADR-026](../07-decisions/ADR-026-fourteen-day-guided-evaluation.md), [ADR-027](../07-decisions/ADR-027-mandatory-mfa-and-step-up-authentication.md), [ADR-028](../07-decisions/ADR-028-customer-lifecycle-and-account-state-model.md)  
Related Releases: None

## Status and Boundary

This entry is **APPROVED PRODUCT / CUSTOMER EXPERIENCE ARCHITECTURE**. It defines the intended customer journey before frontend implementation. It does not claim that authentication, billing, broker connectivity, evaluation entitlements, security controls, or lifecycle automation are implemented.

## Public Entry Paths

The public Landing Page offers three distinct paths:

- **Start 14-Day Guided Evaluation**
- **Subscribe / Create Account**
- **Sign In**

Guided Evaluation and paid Create Account are separate calls to action. There is no anonymous authenticated product access.

## 14-Day Guided Evaluation

The former 7-day customer-trial concept is **SUPERSEDED** by the **14-Day Guided Evaluation**. Engineering references to seven-day validation campaigns are unrelated and remain authoritative for research operations.

Rules:

- Duration is 14 days, limited to one Guided Evaluation per customer.
- Payment method and email verification are required before activation.
- The evaluation is based on Explorer and expires after 14 days unless converted.
- It exposes Command Center, Market Intelligence, Trade Intelligence, and Performance Intelligence with the same core intelligence quality as paid plans.
- Autopilot is unavailable.

The evaluation may preview Professional's approval-required Co-Pilot workflow: StructureIQ may identify an opportunity, prepare a plan, present an approval decision, and demonstrate the workflow, but the user must explicitly approve every execution action. Elite Autopilot may be explained educationally but is not enabled. Unrestricted live broker connectivity or live evaluation execution is not approved or claimed as implemented.

## Paid Account Creation

A paid customer journey is:

1. Choose Explorer, Professional, or Elite.
2. Choose monthly or annual billing.
3. Create Email + Password credentials or use Google Sign-In.
4. Provide payment information.
5. Verify email.
6. Complete required MFA enrollment.
7. Complete onboarding.
8. Enter the Command Center.

No usable protected workspace access is granted until required account, payment, verification, and security steps are complete.

## Billing and Plan Changes

- Billing supports monthly and annual terms; annual billing provides **20% savings**. This architecture does not set prices.
- Upgrades are permitted once successfully billed/authorized and take effect immediately, including the higher plan's permitted execution authority.
- Downgrades take effect at the next billing cycle.
- A customer may change plans only once per billing cycle.
- Handling active higher-tier modes during a pending downgrade remains an implementation detail subject to safeguards.

### Failed Renewal Grace Period

A failed paid renewal enters a seven-day Grace Period. The approved conceptual notification schedule is Day 0 failure, Day 1 reminder, Day 3 reminder, Day 5 final reminder, and Day 7 suspension if unresolved. This is lifecycle architecture, not a claim of hard-coded billing-engine behavior.

### Cancellation

Paid cancellation prevents future renewal while access continues through the current paid billing period; the account then becomes Suspended. Guided Evaluation cancellation or expiration ends access at the evaluation-period boundary.

## Broker and Execution Entitlements

Live broker connections are limited to Professional and Elite. Explorer cannot connect a live broker account. Professional is approval-required assisted execution; Elite may enable optional autonomous execution. The Guided Evaluation does not include unrestricted live broker access. All execution remains subject to authorization, risk, and security safeguards.

## Authentication and Activation

Approved v1 authentication methods are **Email + Password** and **Google Sign-In** only.

Password minimums are eight characters with at least one uppercase letter, one lowercase letter, one number, and one special character. Engineering must use secure modern password hashing and must never store plaintext passwords.

Email verification is mandatory. A Pending Verification user may sign in and reach the Command Center shell, but protected intelligence and meaningful workspace functionality remain locked behind clear verification guidance.

MFA is mandatory for Explorer, Professional, and Elite and is part of activation/onboarding.

## Step-Up Authentication

Fresh authentication/MFA is required for high-risk actions, including connecting or disconnecting a broker, enabling or disabling Autopilot, changing email, password, MFA configuration, or payment method, future API-key management, and other high-risk execution or security settings. Professional approval and Elite Autopilot cannot bypass these safeguards.

## Trusted Devices, Sessions, and Device Management

**Remember This Device** may reduce routine login friction for a conceptual 30-day trust period. Sensitive actions still require step-up authentication.

Security / Device Management may let users view recognized and current devices, last-active time, approximate location, rename or revoke a device, log out a device, and log out all devices.

Conceptual inactivity timeouts are Explorer: 8 hours, Professional: 4 hours, and Elite: 2 hours. Exact token/session mechanics are engineering details; trusted-device status does not remove step-up requirements.

## Security Notifications and Audit History

Security notifications cover at least new login/device, password/MFA/email/payment-method changes, broker connection/disconnection, and Autopilot enablement/disablement. They should include useful time, device, approximate-location context where appropriate and a response path for unauthorized activity.

User-visible and internal audit history may include logins, devices, password/MFA changes, broker actions, subscription changes, AI Authority changes, Autopilot changes, and security locks.

## Abuse Protection and Recovery

Five failed login attempts within approximately 15 minutes may trigger a temporary 15-minute lock; continued suspicious behavior may trigger stronger protections and appropriate notification. This is a conceptual security rule, not an implementation claim.

Recovery architecture includes secure email password reset, recovery codes generated during MFA enrollment, manual recovery when MFA and codes are lost, and a locked-account recovery path. Manual evidence may include verified email ownership, payment/subscription history, account information, and identity verification if necessary. Government ID is not mandatory without future legal/security approval.

## Account States and Permission Model

Conceptual states are Visitor, Pending Registration, Pending Verification, Guided Evaluation, Active Explorer, Active Professional, Active Elite, Grace Period, Suspended, Canceled, Locked, and Deleted.

Effective permissions depend on **Account State + Subscription + AI Authority + Security Status**. State transitions must fail safely and cannot implicitly grant a higher execution authority.

## Account Health

Account Health may show Email Verified, MFA Enabled, Payment Current, Broker Connected where applicable, Trusted Device, and Account Security Status. No numerical health score is approved.

## Retention and Restoration

Inactive or suspended customer history should be retained for approximately 90 days before permanent-deletion processing. Returning customers may restore prior experience within that window where technically and legally permitted. Appropriate deletion notices should be sent. Exact retention, deletion, and restoration rules remain subject to legal and privacy-policy validation.
