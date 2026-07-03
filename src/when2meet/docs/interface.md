# When2Meet API Interface

The When2Meet service provides authenticated APIs for creating events, sharing short event links, and managing participant availability.

## Base URL

- **Hosted:** `https://api.innohassle.ru/when2meet/v0` — [Swagger UI](https://api.innohassle.ru/when2meet/v0/docs)
- **Local development:** `http://localhost:8020/api/v0`

## Authentication

All endpoints require an InNoHassle Accounts Bearer token:

```http
Authorization: Bearer <JWT>
```

## Endpoints

### List My Events

- **URL:** `/events/`
- **Method:** `GET`
- **Response:** `200 OK` — `EventSummary[]`

Returns events owned by the authenticated user. Backend search is not supported; filter by name on the client.

### Create Event

- **URL:** `/events/`
- **Method:** `POST`
- **Request Body:**
  ```json
  {
    "name": "Team Sync",
    "description": "Weekly team synchronization meeting",
    "slots": [
      "2026-06-15T10:00:00Z",
      "2026-06-15T11:00:00Z"
    ],
    "timezone": "Europe/Moscow",
    "specific_time": true,
    "time_range": {
      "start": "10:00",
      "end": "12:00"
    }
  }
  ```
- **Response:** `201 Created` — `EventView`

The backend sets `owner_id` from the token and generates a unique `slug`.

### List Participating Events

- **URL:** `/events/participating`
- **Method:** `GET`
- **Response:** `200 OK` — `EventSummary[]`

Returns events where the authenticated user is a participant but not the owner.

### Get Event

- **URL:** `/events/{event_ref}`
- **Method:** `GET`
- **Path Parameter:** `event_ref` is either an event ObjectId or a short slug.
- **Response:**
  - `200 OK` — `EventView`
  - `404 Not Found` — event does not exist.

### Update Event

- **URL:** `/events/{event_ref}`
- **Method:** `PATCH`
- **Access:** owner only
- **Request Body:** partial `EventUpdate`
- **Response:**
  - `200 OK` — `EventView`
  - `403 Forbidden` — authenticated user is not the owner.
  - `404 Not Found` — event does not exist.

Participant availability is preserved when slots are removed from the event.

### Delete Event

- **URL:** `/events/{event_ref}`
- **Method:** `DELETE`
- **Access:** owner only
- **Response:**
  - `204 No Content`
  - `403 Forbidden` — authenticated user is not the owner.
  - `404 Not Found` — event does not exist.

### Update My Availability

- **URL:** `/events/{event_ref}/participants`
- **Method:** `PUT`
- **Request Body:**
  ```json
  {
    "availability": [
      "2026-06-15T10:00:00Z"
    ]
  }
  ```
- **Response:**
  - `200 OK` — `EventView`
  - `404 Not Found` — event does not exist.

The backend takes participant `user_id` from the Bearer token. Request fields such as `user_id`, `name`, and `if_needed` are rejected.
Availability can include slots outside the current event grid; existing hidden slots are preserved on updates.

### Delete Participant

- **URL:** `/events/{event_ref}/participants/{user_id}`
- **Method:** `DELETE`
- **Access:** event owner or the participant themselves
- **Response:**
  - `200 OK` — `EventView`
  - `403 Forbidden` — authenticated user is neither owner nor participant.
  - `404 Not Found` — event or participant does not exist.

## Data Models

### EventSummary

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | MongoDB ObjectId |
| `slug` | `string` | Short URL-safe event reference |
| `name` | `string` | Event name |
| `description` | `string \| null` | Event description |
| `created_at` | `datetime` | Creation time |
| `participants_count` | `integer` | Number of participants |
| `date_range_label` | `string \| null` | Optional display label |

### EventView

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | MongoDB ObjectId |
| `slug` | `string` | Short URL-safe event reference |
| `name` | `string` | Event name |
| `description` | `string \| null` | Event description |
| `slots` | `list[datetime]` | All possible slots |
| `participants` | `list[ParticipantView]` | Participants with profile data |
| `created_at` | `datetime` | Creation time |
| `timezone` | `string` | IANA timezone name |
| `owner_id` | `string \| null` | InNoHassle Accounts ID of event owner |
| `specific_time` | `boolean` | Whether event has specific time slots |
| `time_range` | `TimeRange \| null` | Optional display/edit metadata |

### ParticipantView

| Field | Type | Description |
| :--- | :--- | :--- |
| `user_id` | `string` | InNoHassle Accounts user ID |
| `email` | `string \| null` | Innopolis email |
| `first_name` | `string \| null` | First name from Telegram or Innopolis profile |
| `last_name` | `string \| null` | Last name from Telegram or Innopolis profile |
| `telegram` | `string \| null` | Telegram `@username` |
| `availability` | `list[datetime]` | Selected slots |

If Accounts lookup fails or a profile is missing, `user_id` and `availability` are still returned and profile fields are `null`.
