# When2Meet API Interface

The When2Meet service provides authenticated APIs for creating meetings, sharing short meeting links, and managing participant availability.

## Base URL

- **Hosted:** `https://api.innohassle.ru/when2meet/v0` — [Swagger UI](https://api.innohassle.ru/when2meet/v0/docs)
- **Local development:** `http://localhost:8020/api/v0`

## Authentication

All endpoints require an InNoHassle Accounts Bearer token:

```http
Authorization: Bearer <JWT>
```

## Endpoints

### List My Meetings

- **URL:** `/meetings/`
- **Method:** `GET`
- **Response:** `200 OK` — `EventSummary[]`

Returns meetings owned by the authenticated user. Backend search is not supported; filter by name on the client.

### Create Meeting

- **URL:** `/meetings/`
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

### List Participating Meetings

- **URL:** `/meetings/participating`
- **Method:** `GET`
- **Response:** `200 OK` — `EventSummary[]`

Returns meetings where the authenticated user is a participant but not the owner.

### Get Meeting

- **URL:** `/meetings/{meeting_ref}`
- **Method:** `GET`
- **Path Parameter:** `meeting_ref` is either a meeting ObjectId or a short slug.
- **Response:**
  - `200 OK` — `EventView`
  - `404 Not Found` — meeting does not exist.

### Update Meeting

- **URL:** `/meetings/{meeting_ref}`
- **Method:** `PATCH`
- **Access:** owner only
- **Request Body:** partial `EventUpdate`
- **Response:**
  - `200 OK` — `EventView`
  - `403 Forbidden` — authenticated user is not the owner.
  - `404 Not Found` — meeting does not exist.

Participant availability is preserved when slots are removed from the meeting.

### Delete Meeting

- **URL:** `/meetings/{meeting_ref}`
- **Method:** `DELETE`
- **Access:** owner only
- **Response:**
  - `204 No Content`
  - `403 Forbidden` — authenticated user is not the owner.
  - `404 Not Found` — meeting does not exist.

### Update My Availability

- **URL:** `/meetings/{meeting_ref}/participants`
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
  - `404 Not Found` — meeting does not exist.

The backend takes participant `user_id` from the Bearer token. Request fields such as `user_id`, `name`, and `if_needed` are rejected.
Availability can include slots outside the current meeting grid; existing hidden slots are preserved on updates.

### Delete Participant

- **URL:** `/meetings/{meeting_ref}/participants/{user_id}`
- **Method:** `DELETE`
- **Access:** event owner or the participant themselves
- **Response:**
  - `200 OK` — `EventView`
  - `403 Forbidden` — authenticated user is neither owner nor participant.
  - `404 Not Found` — meeting or participant does not exist.

### Get Available Rooms

- **URL:** `/meetings/{meeting_id}/available-rooms`
- **Method:** `GET`
- **Response:**
  - `200 OK` — `AvailableRoom[]`
  - `400 Bad Request` — selected meeting time is not set.
  - `404 Not Found` — meeting does not exist.

Returns rooms that are free for the full selected meeting time window and bookable by the authenticated user according to Room Booking rules. Room metadata includes `id`, `name`, `capacity`, and `location`.

## Data Models

### EventSummary

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | MongoDB ObjectId |
| `slug` | `string` | Short URL-safe meeting reference |
| `name` | `string` | Meeting name |
| `description` | `string \| null` | Meeting description |
| `created_at` | `datetime` | Creation time |
| `participants_count` | `integer` | Number of participants |
| `date_range_label` | `string \| null` | Optional display label |

### EventView

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | MongoDB ObjectId |
| `slug` | `string` | Short URL-safe meeting reference |
| `name` | `string` | Meeting name |
| `description` | `string \| null` | Meeting description |
| `slots` | `list[datetime]` | All possible slots |
| `participants` | `list[ParticipantView]` | Participants with profile data |
| `created_at` | `datetime` | Creation time |
| `timezone` | `string` | IANA timezone name |
| `owner_id` | `string \| null` | InNoHassle Accounts ID of meeting owner |
| `specific_time` | `boolean` | Whether meeting has specific time slots |
| `time_range` | `TimeRange \| null` | Optional display/edit metadata |
| `selected_time` | `MeetingTime \| null` | Final time selected by the meeting owner |

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
