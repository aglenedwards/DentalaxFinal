# Dentalax - Dental Practice Directory Platform

## Overview
Dentalax is a Flask-based platform designed to connect patients with dental practices across Germany. It offers a comprehensive directory, appointment booking functionalities, customizable practice landing pages, and subscription models for dental offices. The platform supports dentist and administrator user roles and integrates payment processing via Stripe, aiming to streamline dental care access and practice management in Germany. Patient login has been removed -- patients interact without accounts (reviews via email confirmation, appointments via contact forms).

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Core Technologies
- **Backend:** Flask, Flask-SQLAlchemy (PostgreSQL ORM), Flask-Login (authentication), Flask-WTF (forms).
- **Frontend:** Jinja2 templating, Bootstrap 5 (responsive UI), Font Awesome (icons), AOS (animations), custom CSS.

### Data Model
Key entities include `Zahnarzt` (Dentist), `Patient`, `Praxis` (Practice), `Termin` (Appointment), `Bestandspatient` (Regular Patient), `Stellenangebot` (Job Listing), `Bewerbung` (Application), and `Bewertung` (Review). These models facilitate user management, practice listings, appointment scheduling, patient management, job postings, and patient feedback.

### Key Features
- **Practice Search:** Location-based search with premium placement for subscribed practices and specialization-based prioritization.
- **Practice Landing Pages:** Customizable, SEO-optimized pages for premium subscribers, including details on services, team, and contact information.
- **Subscription Management:** Tiered subscription packages (Basis/Free, Premium €59/month, PremiumPlus €89/month) managed via Stripe.
- **Appointment Booking:** Flexible booking system supporting internal scheduling, external redirects, contact forms, and direct contact options. Month calendar view with color-coded status dots, day detail view, status filters.
  - **Notes per Appointment:** Inline free-text note field on each appointment, editable directly from the list view.
  - **24h Reminder Emails:** Button to send automatic reminder emails to all patients with appointments for the next day. Tracks sent status per appointment.
  - **Day Timeline View:** Toggle between table list view and hourly timeline (7:00-20:00) with color-coded appointment blocks by status.
  - **Recurring Appointments:** Option when creating to repeat weekly, every 2 weeks, every 4 weeks, or monthly, with configurable repeat count (1-52).
- **Bestandspatienten (Regular Patient) System:** Convert guest bookings to regular patients. 6-month recall system with automated email reminders for preventive checkups. Patient history tracking, batch and individual recall sending.
- **Job Listings:** A module for dental job postings, featuring both internal practice listings and aggregated external jobs via TheirStack API, with extensive SEO optimization for city and category pages.
- **Admin Panel:** A comprehensive interface for managing practices, claims, and job listings, with real-time statistics.
- **AI-Powered Tools:**
    - **Dentalberater KI-Chatbot:** An Azure OpenAI-powered (gpt-4.1-mini) dental advisor chatbot with symptom assessment, treatment advice, cost guidance, and intelligent practice matching. Features quick-question chips for common queries, Google Reviews display in practice cards, and 25km geo-filtering with premium/verified prioritization. Includes legal disclaimer (no medical diagnoses). Searches both database and CSV-imported practices.
    - **KI-Praxisassistent:** An AI tool for generating practice descriptions and hero subtitles within the dentist dashboard.
- **SEO Optimization:** 
    - Dedicated SEO pages for dental service specializations (e.g., /implantologie-muenchen) and dynamic sitemap generation.
    - **City SEO Pages (`/zahnarzt-{stadt}`):** AI-generated unique content per city including H1 with tagline, short teaser, two H2 blocks (150-200 words each), FAQ with 4 questions, and meta tags.
    - **Leistung+Stadt SEO Pages (`/{leistung}-{stadt}`):** AI-generated unique content for service+city combinations (e.g., /implantologie-muenchen) including H1, teaser, two H2 blocks, FAQ with 4 questions, and Schema.org FAQPage markup.
    - **Schema.org Markup:** FAQPage JSON-LD for rich snippets, ItemList JSON-LD for dentist listings.
    - **Admin SEO Management (`/admin/seo-texte`):** Interface for single/batch generation (5-50 cities), regeneration of existing texts, with FAQ/Meta status indicators.
    - **Admin Leistung-SEO Management (`/admin/leistung-seo-texte`):** Interface for managing Leistung+Stadt SEO content with tabs per service, single/batch generation (5-50 cities), and regeneration.
- **Claiming Process:** A workflow for dentists to claim and manage their practice listings, including email verification and package selection.

### Design Principles
- **Modular Architecture:** Separation of concerns with dedicated files for routes, models, and integrations.
- **User-Centric UI/UX:** Responsive design with Bootstrap 5, intuitive navigation, and clear calls to action.
- **SEO Focus:** Extensive use of SEO-friendly URLs, meta tags, and schema.org markup for enhanced visibility.

## External Dependencies

### Payment Gateway
- **Stripe:** Used for secure payment processing, managing subscription packages (monthly/yearly billing), and handling customer portal access.

### Database
- **PostgreSQL:** The primary relational database for storing all application data.

### Geocoding
- **Custom Geocoding Utility:** For converting addresses to geographical coordinates, essential for location-based practice search.
- **Google Maps API:** Used for geocoding practice addresses.

### Third-Party APIs
- **TheirStack API:** Integrates external dental job listings from German job boards to enrich the platform's job offerings and SEO content.
- **OpenAI API:** Powers the Dental Match KI-Chatbot for natural language processing and the KI-Praxisassistent for AI text generation.

### File Storage
- **Local Filesystem:** For storing uploaded practice images (e.g., `static/uploads/praxis/`).