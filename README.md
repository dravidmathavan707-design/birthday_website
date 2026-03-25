# Birthday Experience Platform

Flask + MongoDB full-stack application for:
- User authentication (user/admin)
- Friend profile management (name, email, birthday, profile image)
- Daily chat and birthday-locked messages
- Gift planning and countdown tracking
- Cinematic birthday page with reveal, music, balloons, cake, confetti, fireworks, slideshow, messages, and gift section
- Admin visibility across users, friends, chats, gifts, and previews

## Setup

1. Install dependencies:
	- `pip install -r requirements.txt`
2. Set environment variables:
	- `FLASK_SECRET_KEY`
	- `MONGO_URI`
	- `ADMIN_EMAIL`
	- `ADMIN_PASSWORD`
	- `MAIL_SENDER`
	- `MAIL_PASSWORD`
	- `MAIL_SERVER` (default: `smtp.gmail.com`)
	- `MAIL_PORT` (default: `587`)
	- `APP_BASE_URL` (used in email birthday link)
3. Run app:
	- `flask run`

## Main Flows

- User adds friend profiles from dashboard.
- User opens each friend profile to:
  - send daily messages,
  - save birthday messages,
  - plan gifts.
- Birthday messages remain hidden until the friend's birthday.
- Scheduler checks birthdays daily and emails a signed birthday link.
- Signed birthday link opens the cinematic personalized birthday page.
- Admin can preview and access all areas at any time.
