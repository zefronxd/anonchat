class Texts:
    START_WELCOME = "Welcome to the Anonymous Messaging Bot! 🌟\n\nHere, you can chat with others completely anonymously or create your own anonymous link."
    CHOOSE_GENDER = "Please select your gender:"
    GENDER_MALE = "Male 👦"
    GENDER_FEMALE = "Female 👧"
    MAIN_MENU = "Main Menu:"
    MY_LINK = "My Anonymous Link 🔗"
    RANDOM_CHAT = "Random Chat 🎲"
    PROFILE = "My Profile 👤"
    HELP = "Help 📚"
    YOUR_LINK = "Your Anonymous Link:\n{link}"
    WAITING_FOR_MATCH = "Searching for a chat partner... ⏳"
    MATCH_FOUND = "Someone has been found! You can now start chatting. 💬\nSend /stop to end the chat."
    STOP_CHAT = "End Chat 🏁"
    CANCEL_SEARCH = "Cancel Search ❌"
    STOP_SEARCH = "Stop 🛑"
    NEXT_CHAT = "Next ⏭"
    SEND_PROFILE = "Send Profile 👤"
    CHAT_ENDED = "Chat has ended."
    NOT_JOINED = "To use this bot, please join our channel first:\n{channel}"
    CHECK_JOIN = "I've Joined ✅"
    ADMIN_PANEL = "Admin Panel 🛠"
    BROADCAST = "Broadcast 📢"
    ENTER_BROADCAST_MSG = "Please send the message you want to broadcast to all users (text, photo, audio, etc.):"
    STATS = "Bot Statistics 📊"
    ADD_ADMIN = "Add New Admin ➕"
    ENTER_ADMIN_USERNAME = "Please send the new admin's username (without @):"
    ADMIN_ADDED = "User {username} has been successfully promoted to admin. ✅"
    USER_NOT_FOUND = "User not found."

    EDIT_PROFILE = "Edit Profile 📝"
    EDIT_BIO = "Change Bio 🖋"
    EDIT_AGE = "Change Age 🎂"
    ENTER_AGE = "Please enter your age in numbers (e.g., 25):"
    AGE_UPDATED = "Your age has been successfully updated. ✅"
    ENTER_BIO = "Please write your new bio (maximum 100 characters):"
    BIO_UPDATED = "Your bio has been successfully updated. ✅"
    CHANGE_GENDER = "Change Gender 🚻"

    # Advanced Admin
    SET_CHANNEL = "Set Channel Lock 🔒"
    ENTER_CHANNEL_ID = "Send the channel's numeric ID or username (e.g., -100123...):"
    CHANNEL_UPDATED = "Channel lock has been successfully updated. ✅"
    SEARCH_LOGS = "Search User Messages 🔍"
    ENTER_USER_ID = "Please enter the numeric ID of the user:"
    EXPORT_USERS = "Export User List 📂"
    USER_LOGS_HEADER = "Messages of user {user_id}:"

    # Reply System
    REPLY = "Reply 💬"
    CLOSE_RELAY = "Close Chat ❌"
    REPLY_PROMPT = "Preparing to send a reply... Please write the message you want to send to the anonymous user:"

    # Profile Expansion
    EDIT_NICKNAME = "Change Nickname 🎭"
    ENTER_NICKNAME = "Enter your new nickname:"
    NICKNAME_UPDATED = "Your nickname has been successfully updated. ✅"

    # Block System
    BLOCK_USER = "Block User 🚫"
    USER_BLOCKED = "User has been blocked and the conversation has ended. 🚫"
    YOU_ARE_BLOCKED = "Unfortunately, your chat partner has blocked you. The conversation has ended. 😔"
    BLOCK_LIST = "Blocked Users 🚫"
    NO_BLOCKS = "Your block list is empty."
    UNBLOCK_SUCCESS = "User {name} has been removed from your block list. ✅"
    CONFIRM_BLOCK = "Are you sure you want to block this user?"

    # Referral System
    REFERRAL_MENU = "Referral Link 🎁"
    REFERRAL_INFO = (
        "<b>🎁 Referral System & Rewards:</b>\n\n"
        "Invite your friends to the bot and earn special rewards!\n"
        "Once you reach <b>30 referrals</b>, you can request to have <b>your personal channel</b> locked in the bot for <b>1 hour</b> (free promotion for your channel). ✅\n\n"
        "🔗 <b>Your Referral Link:</b>\n<code>{link}</code>\n\n"
        "📊 <b>Your Statistics:</b>\n"
        "👤 Total Invited Users: <b>{count}</b>"
    )
    CLAIM_REWARD = "Claim Reward 🎁"
    CLAIM_REWARD_MSG = (
        "🎉 <b>Congratulations!</b>\n\n"
        "You have reached 30 referrals and are now eligible to claim your reward.\n"
        "To arrange the activation of your channel lock in the bot, please contact the following username:\n\n"
        "🆔 @cryptex_here"
    )
