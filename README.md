# CreatorPay - Revenue Distribution Engine

A high-fidelity, Neubrutalist-styled platform for managing creator revenue distribution with built-in bot resistance and community transparency.

## 🚀 Key Features
- **Multi-Role Ecosystem**: Dedicated dashboards for Admins, Creators, and Viewers.
- **Bot Resistance Engine**: Advanced tracking of "Total Views" vs "Unique Human Clicks" to prevent refresh-spamming.
- **Indian Rupee (₹) Localization**: All financial reporting and payouts are natively in INR.
- **Live Transparency**: Real-time leaderboards and payout breakdowns for the community.
- **Neubrutalist UI**: Premium aesthetic with haptic feedback and high-contrast design.

## 🛠️ Tech Stack
- **Backend**: Python (Flask)
- **Database**: Supabase (PostgreSQL)
- **Styling**: Vanilla CSS (Neubrutalism)
- **Authentication**: Custom Role-Based Auth with direct Supabase REST integration.

## 📦 Setup & Installation
1. **Clone the Repo**:
   ```bash
   git clone https://github.com/your-username/creatorpay.git
   cd creatorpay
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment**:
   - Rename `.env.example` to `.env`.
   - Add your `SUPABASE_URL` and `SUPABASE_KEY`.
4. **Database Setup**:
   - Run the code in `supabase_schema.sql` within your Supabase SQL Editor.
5. **Run Locally**:
   ```bash
   python app.py
   ```

## 🛡️ Security Note
For production deployment, ensure that **Row Level Security (RLS)** is enabled on all Supabase tables and appropriate policies are configured to protect user data.
