# Sprint Review Transcript

### Discussion of Sprint 3 (design updates and meeting creation functionality)

00:00:01

**Vladislav Konovalov:** Hi! This sprint has been focused on improving the app design and user experience. Now I'll show you how creating and editing a meeting works. The basic creation process hasn't changed: we still select the day and time slots.

00:00:32

**Vladislav Konovalov:** However, if you select the option to specify time slots for each day, the next screen now pulls events from the calendar. They are displayed so the user is alerted and doesn't accidentally select a time when they're already busy.

00:00:55

**Customer:** Is this pulled from your personal calendar?

00:00:57

**Vladislav Konovalov:** Yes, the data is pulled from your personal calendar in InnoHassle. You can hover over an event to see the details.

00:01:03

**Customer:** Does this work on the phone?

00:01:07

**Vladislav Konovalov:** Yes, you can also view information about the event on the mobile version.

00:01:12

**Customer:** Is it still possible to schedule a meeting for this time?

00:01:14

**Vladislav Konovalov:** Yes, you can schedule it for any time; this is just an informational alert. After saving the time slot, the meeting menu opens.

00:01:41

**Vladislav Konovalov:** Here you'll see a list of participants who have responded, and you can mark your exact available time. Calendar events are only displayed when you select your own time.

00:02:17

**Customer:** Maybe we should add a button to hide these events from the calendar? What if the person doesn't attend classes at all, and this information just distracts them?

00:02:26

**Vladislav Konovalov:** Okay, we'll add this feature in the next sprint. Now let's see what a meeting looks like with already filled slots. Your selected time is now clearly outlined with a border, making it easy to distinguish from other participants' responses. A filter has also been added to show only those slots with a certain number of people available.

00:03:14

**Customer:** The filter is great, but I'm not sure the border selection is intuitive. It looks good, but we need to add a legend or somehow visually emphasize that this is my time.

00:03:28

**Vladislav Konovalov:** Agreed, we'll add a small legend at the bottom explaining that the box represents your time slot, while the regular fill represents the total time slot for all participants. Then, after participants have filled in their time slots, they can book a room directly on the heatmap through the InnoHassle system.

00:04:07

**Customer:** Right now, this action isn't clear. The button is green, and I don't understand what the system expects from me or what just happened. Booking itself shouldn't be mandatory. I'd like to see a separate window with the logic: "Let's create a meeting, choose a time. If you want, we'll reserve a room, and then send the event to the calendar for all available participants." As it stands, everything is unclear.

00:04:39

**Vladislav Konovalov:** We thought long and hard about the mechanics and decided that selecting the time directly on the heat map would be most convenient, since a simple list of options isn't as clear.

00:04:54

**Customer:** However, right now the page state is opaque, and it is unclear what exactly is required from the user.

00:04:59

**Vladislav Konovalov:** Okay, we will add more explanatory information for the user.

00:05:11

**Vladislav Konovalov:** After choosing the time, you can select a free room from the list and confirm the reservation.

00:05:23

**Customer:** The drop-down list looks strange and doesn't match the design elements of the rest of the site.

00:05:28

**Vladislav Konovalov:** This is a standard native browser drop-down list. After using it, the booking for our meeting is created. This completes the sprint's workflow, and the created meeting should now appear in the calendar.

00:06:10

**Customer:** I need a link to the meeting added to it so I can jump right into it. And another question: was this meeting added to the calendar for all available participants?

00:06:22

**Vladislav Konovalov:** No, the room booking functionality does not support this yet.

00:06:33

**Customer:** This needs to be fixed. The event needs to appear in the calendars of all available participants, not just the creator.

00:06:41

**Vladislav Konovalov:** This will require linking the booking logic to the meeting, as they currently exist separately. We'll do this, add a link, and implement a calendar push.

### UAT results

00:07:13

**Vladislav Konovalov:** Now let's move on to acceptance tests. The first test verifies that when selecting a time, the user sees their current events from the calendar. As I've already demonstrated, existing events and their details are correctly displayed when selecting a time.

00:07:47

**Vladislav Konovalov:** The second test checks the ability to search for participants, view their available time, and remove them from a meeting. I opened a meeting with a large number of participants; the list now appears more compact.

00:08:18

**Vladislav Konovalov:** At the moment, only email is displayed here.

00:08:22

**Customer:** This is sad.

00:08:26

**Vladislav Konovalov:** Searching the list works correctly. You can select one or more participants to view their individual availability. If you're the meeting owner, you can remove participants.

00:08:58

**Customer:** I didn't see the delete confirmation button. What if I clicked it by accident?

00:09:04

**Vladislav Konovalov:** Fair enough, we'll add a confirmation window before deleting. The third test confirms the ability to reserve a free room for the selected time.

00:09:33

**Vladislav Konovalov:** I've already demonstrated this functionality: we can choose a time, find an available room, and book it. I think that's all. Is there any other feedback?

00:09:59

**Customer:** It seems there is nothing else.
