import json
import os
from datetime import datetime

# ============================================
# BOT KI MEMORY — Har cheez yaad rakhta hai
# ============================================

MEMORY_FILE = "bot_memory.json"

def load_memory() -> dict:
    """Memory file load karo"""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    
    # Default memory structure
    return {
        "version": 1,
        "created": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        
        # Task history
        "tasks": {
            "applied": [],      # Apply kiye tasks
            "won": [],          # Mile tasks
            "completed": [],    # Complete kiye tasks
            "rejected": [],     # Client ne reject kiye
            "skipped": []       # Bot ne skip kiye
        },
        
        # Learning data
        "learning": {
            "successful_task_types": {},   # Konse tasks milte hain
            "failed_task_types": {},       # Konse tasks nahi milte
            "avg_price_won": 0,            # Average price jo milti hai
            "best_cover_letter_style": "", # Kaunsa style kaam karta hai
            "client_feedback": [],         # Client ke comments
            "rejection_reasons": []        # Reject kyun hue
        },
        
        # Performance stats
        "stats": {
            "total_applied": 0,
            "total_won": 0,
            "total_completed": 0,
            "total_earned": 0,
            "win_rate": 0,
            "completion_rate": 0,
            "avg_client_rating": 0,
            "days_active": 0,
            "best_day": "",
            "best_category": ""
        },
        
        # Bot ki evolved strategy
        "strategy": {
            "min_price": 5,
            "preferred_categories": [],
            "avoided_categories": [],
            "cover_letter_tips": [],
            "best_time_to_apply": "",
            "current_level": "beginner"  # beginner -> intermediate -> expert
        }
    }

def save_memory(memory: dict):
    """Memory save karo"""
    memory['last_updated'] = datetime.now().isoformat()
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

def record_applied(memory: dict, task: dict, cover_letter: str):
    """Task apply hone pe record karo"""
    memory['tasks']['applied'].append({
        "id": task.get('id'),
        "title": task.get('title'),
        "price": task.get('price'),
        "category": task.get('category', 'unknown'),
        "cover_letter": cover_letter[:200],
        "applied_at": datetime.now().isoformat()
    })
    memory['stats']['total_applied'] += 1
    
    # Win rate update
    if memory['stats']['total_applied'] > 0:
        memory['stats']['win_rate'] = round(
            memory['stats']['total_won'] / memory['stats']['total_applied'] * 100, 1
        )
    save_memory(memory)

def record_won(memory: dict, task: dict):
    """Task mile pe record karo"""
    memory['tasks']['won'].append({
        "id": task.get('id'),
        "title": task.get('title'),
        "price": task.get('price'),
        "category": task.get('category', 'unknown'),
        "won_at": datetime.now().isoformat()
    })
    memory['stats']['total_won'] += 1
    
    # Successful task type track karo
    category = task.get('category', 'unknown')
    if category not in memory['learning']['successful_task_types']:
        memory['learning']['successful_task_types'][category] = 0
    memory['learning']['successful_task_types'][category] += 1
    
    # Best category update
    best_cat = max(
        memory['learning']['successful_task_types'],
        key=memory['learning']['successful_task_types'].get
    )
    memory['strategy']['best_category'] = best_cat
    memory['stats']['best_category'] = best_cat
    
    # Win rate update
    if memory['stats']['total_applied'] > 0:
        memory['stats']['win_rate'] = round(
            memory['stats']['total_won'] / memory['stats']['total_applied'] * 100, 1
        )
    
    save_memory(memory)

def record_completed(memory: dict, task: dict, client_rating: int = 0, feedback: str = ""):
    """Task complete hone pe record karo"""
    memory['tasks']['completed'].append({
        "id": task.get('id'),
        "title": task.get('title'),
        "price": task.get('price'),
        "rating": client_rating,
        "feedback": feedback,
        "completed_at": datetime.now().isoformat()
    })
    
    memory['stats']['total_completed'] += 1
    memory['stats']['total_earned'] += task.get('price', 0)
    
    # Client feedback save karo
    if feedback:
        memory['learning']['client_feedback'].append({
            "task": task.get('title'),
            "feedback": feedback,
            "rating": client_rating,
            "date": datetime.now().isoformat()
        })
    
    # Rating update
    ratings = [t.get('rating', 0) for t in memory['tasks']['completed'] if t.get('rating')]
    if ratings:
        memory['stats']['avg_client_rating'] = round(sum(ratings) / len(ratings), 1)
    
    # Level update
    memory['strategy']['current_level'] = get_level(memory)
    
    save_memory(memory)

def record_rejected(memory: dict, task: dict, reason: str = ""):
    """Reject hone pe record karo"""
    memory['tasks']['rejected'].append({
        "id": task.get('id'),
        "title": task.get('title'),
        "price": task.get('price'),
        "reason": reason,
        "rejected_at": datetime.now().isoformat()
    })
    
    # Failed task type track karo
    category = task.get('category', 'unknown')
    if category not in memory['learning']['failed_task_types']:
        memory['learning']['failed_task_types'][category] = 0
    memory['learning']['failed_task_types'][category] += 1
    
    if reason:
        memory['learning']['rejection_reasons'].append(reason)
    
    save_memory(memory)

def get_level(memory: dict) -> str:
    """Bot ka current level"""
    completed = memory['stats']['total_completed']
    earned = memory['stats']['total_earned']
    rating = memory['stats']['avg_client_rating']
    
    if completed >= 20 and earned >= 200 and rating >= 4.5:
        return "expert"
    elif completed >= 5 and earned >= 50:
        return "intermediate"
    else:
        return "beginner"

def get_performance_report(memory: dict) -> str:
    """Performance report banao"""
    stats = memory['stats']
    strategy = memory['strategy']
    learning = memory['learning']
    
    level_emoji = {
        "beginner": "🌱",
        "intermediate": "⚡",
        "expert": "🏆"
    }
    
    report = f"""
📊 **Bot Performance Report**
━━━━━━━━━━━━━━━━━━━━
{level_emoji.get(strategy['current_level'], '🌱')} Level: **{strategy['current_level'].upper()}**

📈 **Stats:**
• Total Applied: {stats['total_applied']}
• Tasks Won: {stats['total_won']}
• Completed: {stats['total_completed']}
• Win Rate: {stats['win_rate']}%
• Total Earned: ${stats['total_earned']}
• Avg Rating: {stats['avg_client_rating']}/5

🎯 **Best Category:** {stats.get('best_category', 'Learning...')}

🧠 **What Bot Learned:**
• Successful: {list(learning['successful_task_types'].keys())[:3]}
• Avoiding: {list(learning['failed_task_types'].keys())[:3]}

⚙️ **Current Strategy:**
• Min Price: ${strategy['min_price']}
• Preferred: {strategy['preferred_categories'][:3]}
━━━━━━━━━━━━━━━━━━━━
"""
    return report

def evolve_strategy(memory: dict) -> dict:
    """Bot khud apni strategy improve kare"""
    
    # Agar 5+ tasks complete ho gaye to strategy update karo
    if memory['stats']['total_completed'] >= 5:
        
        # Successful categories prefer karo
        if memory['learning']['successful_task_types']:
            top_categories = sorted(
                memory['learning']['successful_task_types'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            memory['strategy']['preferred_categories'] = [c[0] for c in top_categories]
        
        # Failed categories avoid karo
        if memory['learning']['failed_task_types']:
            bad_categories = list(memory['learning']['failed_task_types'].keys())
            memory['strategy']['avoided_categories'] = bad_categories
        
        # Min price adjust karo based on experience
        if memory['stats']['total_completed'] >= 10:
            memory['strategy']['min_price'] = 10  # Intermediate: $10 minimum
        if memory['stats']['total_completed'] >= 20:
            memory['strategy']['min_price'] = 15  # Expert: $15 minimum
        
        # Cover letter tips add karo based on feedback
        positive_feedback = [
            f for f in memory['learning']['client_feedback']
            if f.get('rating', 0) >= 4
        ]
        if positive_feedback:
            memory['strategy']['cover_letter_tips'] = [
                f"Style that worked: {f['task']}" 
                for f in positive_feedback[:3]
            ]
    
    save_memory(memory)
    return memory
