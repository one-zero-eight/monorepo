# Customer Meeting Transcript

Sanitized English transcript of the Week 2 customer review meeting. Timestamps are on separate lines.

---

**Interview and discussion of additional issues**

00:00:01

**Nikita Lisitskiy:** We didn't have time to cover all the questions last time, and we've accumulated some new ones, so let's discuss them again. First, which specific services should be integrated with our product?

**Customer:** It should be Maps. Probably room booking. Maps will store a link to the venue. We click on the venue and see where it is on the map. Room booking could probably be integrated somehow so that once the meeting has settled, we can find an available space. And a calendar, so we can see the availability of participants, and then return the event we create to the calendar.

00:00:56

**Nikita Lisitskiy:** The next question is about notifications. Should we implement them, and if so, how? Perhaps email, Telegram, or push notifications?

**Customer:** InnoHassle doesn't currently have any kind of notification system. The only way we send notifications is via email. But think about it, it's probably a bit inconvenient to receive them in my email in Outlook. We don't have push notifications, and we're still figuring that out, so we haven't even addressed the issue within our main projects. We don't yet have a Telegram bot like most students have, so it seems you currently have nowhere to send notifications.

00:01:54

**Nikita Lisitskiy:** Are there any established conventions regarding endpoint naming, versioning?

**Customer:** I think you'll figure it out by looking at existing endpoints and talking to the technical team. This isn't for me, but for the other guys and from [one-zero-eight](https://github.com/one-zero-eight).

00:02:18

**Nikita Lisitskiy:** Is there a design team or is there some kind of figma mockup or do we need to provide the design ourselves based on the existing InnoHassle design system?

**Customer:** You need to look at InnoHassle and strive to reuse existing components as much as possible, so that at least you don't invent from scratch.

---

**Demonstration of the prototype and discussion of functionality**

00:03:04

**Mikhail Istomin:** I've prepared a mock mobile version because when2meet will be used mostly on phones. Last time, we came up with something called "open meetings"—open meetings (like office hours). You can create an open meeting, it will be visible in the list, and someone will come in, see it, and sign up. You can also add other meetings there (like a Dota tournament) so you can see the organizer, message them, and join.

**Customer:** We're removing open meetings; when2meet can't have such a platform. Essentially, when you organize an event for a large number of people, you set the time yourself as hosts. Access will be blocked in any case. We're removing this page.

00:05:07

**Mikhail Istomin:** Let's move on to creating and managing our meetings. When creating a meeting, a menu appears where you can enter a name and add a password in case the link gets leaked to third parties. You can also specify specific times.

**Customer:** Is this password needed for user identification? I don't really understand the point.

**Nikita Lisitskiy:** For example, if there are already people in the audience, you can schedule a meeting just for them and verbally communicate the password.

**Customer:** If the link gets leaked, the host will simply look at the list of registered users and remove any unnecessary ones. Moreover, we already identify people by their identity in InnoHassle. I don't see the point of a password yet.

**Mikhail Istomin:** Fair enough, let's remove the password. Regarding time selection, you can select days and time slots in the calendar. Clicking "Next" takes the organizer to a page where they select a time for each specific day. The created event page will have a list of all responses, where you can see which time is convenient for everyone.

00:07:40

**Customer:** Response search is missing.

**Mikhail Istomin:** Drawing this in Figma would have taken 20–30 minutes. I didn't draw any more screens. At the bottom there will be a list of participants where you can delete people or edit their times. Registered users will also be able to edit their times.

**Customer:** Typically, prototypes start with writing out all the pages and sketching them out. There's not even a page for creating a meeting place.

**Mikhail Istomin:** We're still just imagining the remaining functionality. When creating, you'll be able to select a room in advance or book it later, when you can see what time is convenient for everyone via the link.

**Customer:** We discussed everything we could.
