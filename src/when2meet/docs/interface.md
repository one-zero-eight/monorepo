# When2Meet API Interface

The When2Meet service provides an API for creating events and managing participant availability.

## Base URL

By default, the service runs on `http://localhost:8020`.

## Endpoints

### 1. Create Event

Create a new event with a list of available time slots.

- **URL:** `/events/`
- **Method:** `POST`
- **Request Body:**
  ```json
  {
    "name": "Team Sync",
    "description": "Weekly team synchronization meeting",
    "slots": [
      "2023-11-01T10:00:00Z",
      "2023-11-01T11:00:00Z",
      "2023-11-02T14:00:00Z"
    ]
  }
  ```
- **Response:**
  - `201 Created`: Returns the created [Event](#event-object) object.

---

### 2. Get Event

Retrieve details about an event, including all participants' availability.

- **URL:** `/events/{event_id}`
- **Method:** `GET`
- **Response:**
  - `200 OK`: Returns the [Event](#event-object) object.
  - `404 Not Found`: Event with the given ID does not exist.

---

### 3. Update Participant Availability

Add or update a participant's availability for a specific event.

- **URL:** `/events/{event_id}/participants`
- **Method:** `PUT`
- **Request Body:**
  ```json
  {
    "name": "John Doe",
    "availability": [
      "2023-11-01T10:00:00Z",
      "2023-11-02T14:00:00Z"
    ]
  }
  ```
- **Response:**
  - `200 OK`: Returns the updated [Event](#event-object) object.
  - `400 Bad Request`: One or more slots in the availability list are not part of the event's defined slots.
  - `404 Not Found`: Event with the given ID does not exist.

---

## Data Models

### Event Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | MongoDB ObjectID |
| `name` | `string` | Name of the event |
| `description` | `string` (nullable) | Description of the event |
| `slots` | `list[datetime]` | All possible slots for the event |
| `participants` | `list[Participant]` | List of participants and their selected slots |
| `created_at` | `datetime` | When the event was created |

### Participant Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Name of the participant |
| `availability` | `list[datetime]` | Slots the participant is available for |
