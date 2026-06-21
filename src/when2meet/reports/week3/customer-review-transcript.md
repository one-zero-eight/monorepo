# Customer Sprint Review Transcript

Sanitized English transcript of the Week 3 Sprint Review (20 June 2026). Timestamps are on separate lines. Recording is instructor-only; see [customer-review-summary.md](customer-review-summary.md).

---

## Demonstration of the MVP and discussion of the implemented functionality

00:00:01

**Nikita Lisitskiy:** Hello! It's been three weeks, and we have a ready-made MVP. Initially, we selected three key features that we considered most relevant: creating a new meeting, sharing a link for other participants to join, attendance tracking, and viewing a heatmap. Currently, we've implemented meeting creation with an interactive frontend, where you can set a name, an optional description, and select a time period. This time period (for example, from 9:00 AM to 5:00 PM) is shared across all selected days.

00:01:53

**Nikita Lisitskiy:** After creating a meeting, a window appears, allowing us to share the link with other participants. We can't demonstrate the full sharing functionality at this time, as the project is only deployed locally, but testing has shown that it works. In the interface, you can manually add a new participant and mark their available time slot on the heatmap, selecting "Available" or "If needed." Participants can be easily removed. After saving slots, you can return to editing them. Hovering over a slot displays a tooltip indicating the number of people who can attend that time. You can also search for participants and click the "View All" button.

## Feedback from the customer and discussion of improvements

00:04:07

**Customer:** I have some comments. First, the "Specific time" button at the entrance is completely unclear. Apparently, it means you can set a different time for each individual day, but the wording itself is unclear.

00:04:21

**Nikita Lisitskiy:** Yes, I agree. Specific time slots can be selected after the meeting is created.

00:04:51

**Customer:** Secondly, it's unclear in the meeting itself why we're manually adding participants. I assumed participants would be linked to SSO and their profiles, so that random people couldn't be added and everything would be transparent. The current manual adding mechanism is unclear to me. It's also unclear how the "Best Time" button works.

00:04:59

**Nikita Lisitskiy:** Right now, simply sharing the link isn't an option. Unfortunately, Misha couldn't attend today, so I'll check with him later. Regarding the "Best Time" button, it apparently suggests the most suitable time by simply showing the first intersection of slots at the top.

00:06:22

**Customer:** It's great that you came up with this, but in its current form it's useless. It's a minus. Instead of a "Best Time" button, it would be better to create a filter. For example, if we have 30 people, it will be difficult for me to distinguish shades of purple, so the filter should only include the intersection with the largest number of people. I think I've covered everything.

00:07:04

**Nikita Lisitskiy:** Okay, thank you. The team has no more questions for the client.
