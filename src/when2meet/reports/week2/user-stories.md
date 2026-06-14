# User Stories

## Personas

| Persona | Description |
| --- | --- |
| **Meeting organizer** | An InnoHassle user who creates a meeting, defines candidate time slots, shares a link, reviews responses, and finalizes time/room. |
| **Meeting participant** | An InnoHassle user who opens a shared meeting link and marks availability. |

## Initial proposed MVP v1 scope

Selected **Must Have** stories for the first deliverable:

- **US-001** — create a new meeting with predefined time options
- **US-002** — share a meeting to collect participant availability
- **US-003** — join via link and submit comfortable times
- **US-006** — view participant opinions on a heat map

## US-001: Create a new meeting

**Requirement status:** Active  
**MoSCoW priority:** Must Have

As a meeting organizator,  
I want to create a new meeting,  
so that I will predefine appropriate time.

### Notes and constraints

- Organizer selects days and time slots in the calendar (approved in customer meeting).
- Backend: `POST /api/v0/events/` in MVP v0; mobile flow in [Figma prototype](https://www.figma.com/design/Q31P4ba6YlmTOzoXC3W3E7/Untitled?node-id=0-1&t=8UaoXVNW08qHuwuY-1).
- Meeting password removed from prototype per customer feedback.

## US-002: Share a meeting

**Requirement status:** Active  
**MoSCoW priority:** Must Have

As a meeting organizator,  
I want to share a meeting,  
so that I will collect users opinions about their comfortable time.

### Notes and constraints

- Shareable link is the primary distribution mechanism.
- Host controls unwanted participants via InnoHassle identity, not link passwords.

## US-003: Join meeting and submit availability

**Requirement status:** Active  
**MoSCoW priority:** Must Have

As a meeting participant,  
I want to connect to the meeting via link, and put time that appropriate to me to share my opinion with other participants,  
so that the organizer can see when I am available.

### Notes and constraints

- MVP v0: `PUT /api/v0/events/{id}/participants`.
- Participant may only select slots predefined by the organizer.

## US-004: See calendar events while choosing time

**Requirement status:** Active  
**MoSCoW priority:** Should Have

As a meeting participant,  
I want to connect be aware about events in my calendar during shoosing time for meeting,  
so that I will avoid events collision.

### Notes and constraints

- Maps to customer request for calendar integration (see meeting transcript).
- Depends on InnoHassle calendar API; not in initial MVP v1 scope.

## US-005: MEOW button

**Requirement status:** Active  
**MoSCoW priority:** Won't Have

Provide a MEOW button, to make a funny kitten sound.

### Notes and constraints

- Not part of MVP v1 or customer-facing roadmap.

## US-006: View availability heat map

**Requirement status:** Active  
**MoSCoW priority:** Must Have

As a meeting participant,  
I want to see other participants opinion on the heat map, to know which time is relevant for them.

### Notes and constraints

- Corresponds to aggregated responses / results view discussed with customer.
- MVP v0: `GET /api/v0/events/{id}` returns participant availability for aggregation; heat-map UI in Figma/hosted frontend.

## US-007: Book a room for the best time

**Requirement status:** Active  
**MoSCoW priority:** Should Have

As a meeting organizator,  
I want to book a room within best time,  
so that I will not spend time seeking available room.

### Notes and constraints

- Customer discussed room booking after consensus or during creation.
- Integrates with InnoHassle room-booking service when available.

## US-008: Organizer reminders to participants

**Requirement status:** Active  
**MoSCoW priority:** Could Have

As a meeting organizator,  
I want to have an opportunity to provide a reminder to users about the meeting, so they will be engaged to provide their responses.

### Notes and constraints

- Customer noted InnoHassle has no push/Telegram channel; email-only is inconvenient.
- Deferred until platform notification infrastructure exists.

## US-009: Participant reminders to pick time

**Requirement status:** Active  
**MoSCoW priority:** Could Have

As a meeting participant,  
I want to recieve a reminders about picking time, so I will not forget about giving availability feedback.

### Notes and constraints

- Same delivery-channel constraints as US-008.

## US-010: Edit or cancel a meeting

**Requirement status:** Active  
**MoSCoW priority:** Could Have

As a meeting organizer,  
I want to be able to edit the details of an existing meeting (such as name and description) or cancel it entirely,  
so that I can adapt to changing plans and prevent participants from interacting with outdated or unnecessary events.

### Notes and constraints

- Not implemented in MVP v0 API.
- Customer meeting discussed editing participant times; full meeting edit/cancel is a later enhancement.
