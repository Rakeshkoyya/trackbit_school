"""The CBSE-shaped content bank for the big-school pack.

Chapter titles follow the NCERT books a CBSE school actually uses (Marigold /
Rimjhim / Vasant / Math-Magic / Looking Around / Honeysuckle / Honeycomb /
Honeydew / Ruchira), plus the grammar, writing, computer, art and PE units a
school adds on top of them. Topic titles come from a per-subject teaching
template, because no school writes 2,000 unique sub-topic names — they write a
chapter and teach it in the same three or four moves.

Separate from `generate.py` so the numbers (period splits, teacher loads,
calendar) stay readable next to the machinery that consumes them.
"""

from __future__ import annotations

# ── how each subject is taught, one period-block at a time ───────────────────
# The pack's topics are these, cycled per chapter. Deliberately generic: they
# are what a teacher logs ("did the comprehension today"), not invented detail.
TOPIC_TEMPLATE: dict[str, list[str]] = {
    "English": ["Reading and comprehension", "New words and meanings",
                "Questions and discussion", "Writing and application"],
    "Hindi": ["Paath vachan", "Shabdarth aur prashnottar",
              "Vyakaran abhyas", "Lekhan abhyas"],
    "Mathematics": ["Concept introduction", "Worked examples",
                    "Practice exercises", "Word problems and revision"],
    "EVS": ["Observation and discussion", "Key ideas", "Activity and worksheet"],
    "Science": ["Concept and explanation", "Activity or demonstration",
                "Textbook exercises", "Revision and quiz"],
    "Social Studies": ["Reading and key ideas", "Map and source work",
                       "Discussion", "Exercises and revision"],
    "Sanskrit": ["Paath vachan", "Shabdarth", "Vyakaran abhyas"],
    "Computer Science": ["Concept discussion", "Lab practice", "Skill check"],
    "Art & Craft": ["Demonstration", "Studio practice", "Display and review"],
    "Physical Education": ["Warm-up and drill", "Skill practice",
                           "Game and assessment"],
}


# ── chapters, per subject per grade ──────────────────────────────────────────
CHAPTERS: dict[str, dict[int, list[str]]] = {}

CHAPTERS["English"] = {
    1: [  # Marigold 1
        "A Happy Child", "Three Little Pigs", "After a Bath",
        "The Bubble, the Straw and the Shoe", "One Little Kitten",
        "Lalu and Peelu", "Once I Saw a Little Bird", "Mittu and the Yellow Mango",
        "Merry-Go-Round", "Circle", "If I Were an Apple", "Our Tree",
        "Sundari", "A Little Turtle", "The Tiger and the Mosquito",
        "Grammar: Naming Words", "Grammar: Doing Words",
    ],
    2: [  # Marigold 2
        "First Day at School", "Haldi's Adventure", "I Am Lucky!", "I Want",
        "A Smile", "The Wind and the Sun", "Rain", "Storm in the Garden",
        "Zoo Manners", "Funny Bunny", "Mr Nobody", "Curlylocks and the Three Bears",
        "I Am the Music Man", "The Mumbai Musicians", "The Magic Porridge Pot",
        "Grammar: Naming and Describing Words", "Writing: Picture Composition",
    ],
    3: [  # Marigold 3
        "Good Morning", "The Magic Garden", "Bird Talk", "Nina and the Baby Sparrows",
        "Little by Little", "The Enormous Turnip", "Sea Song", "A Little Fish Story",
        "The Balloon Man", "The Yellow Butterfly", "Trains", "The Story of the Road",
        "Puppy and I", "Little Tiger, Big Tiger", "What's in the Mailbox?",
        "Grammar: Nouns and Pronouns", "Writing: Sentences and Paragraphs",
    ],
    4: [  # Marigold 4
        "Wake Up!", "Neha's Alarm Clock", "Noses", "The Little Fir Tree", "Run!",
        "Nasruddin's Aim", "Why?", "Alice in Wonderland", "Don't be Afraid of the Dark",
        "Helen Keller", "The Donkey", "Hiawatha", "The Milkman's Cow",
        "The Scholar's Mother Tongue", "The Giving Tree",
        "Grammar: Verbs and Tenses", "Writing: Informal Letter",
    ],
    5: [  # Marigold 5
        "Ice-cream Man", "Wonderful Waste!", "Teamwork", "Flying Together",
        "My Shadow", "Robinson Crusoe Discovers a Footprint", "Crying",
        "My Elder Brother", "The Lazy Frog", "Rip Van Winkle",
        "The Talkative Barber", "Topsy-turvy Land", "Gulliver's Travels",
        "Nobody's Friend", "The Little Bully", "Sing a Song of People",
        "Grammar: Adjectives and Adverbs", "Writing: Paragraph and Notice",
    ],
    6: [  # Honeysuckle 6
        "Who Did Patrick's Homework?", "A House, A Home",
        "How the Dog Found Himself a New Master", "The Kite", "Taro's Reward",
        "The Quarrel", "An Indian-American Woman in Space: Kalpana Chawla",
        "Beauty", "A Different Kind of School", "Where Do All the Teachers Go?",
        "Who I Am", "The Wonderful Words", "Fair Play", "Vocation",
        "A Game of Chance", "Desert Animals", "The Banyan Tree",
        "Grammar: Sentences, Nouns and Pronouns", "Writing: Formal and Informal Letters",
    ],
    7: [  # Honeycomb 7
        "Three Questions", "The Squirrel", "A Gift of Chappals", "The Rebel",
        "Gopal and the Hilsa Fish", "The Shed",
        "The Ashes That Made Trees Bloom", "Chivvy", "Quality", "Trees",
        "Expert Detectives", "Mystery of the Talking Fan",
        "The Invention of Vita-Wonk", "Fire: Friend and Foe",
        "A Bicycle in Good Repair", "The Story of Cricket",
        "Grammar: Determiners, Modals and Voice", "Writing: Notice, Message and Diary",
    ],
    8: [  # Honeydew 8
        "The Best Christmas Present in the World", "The Ant and the Cricket",
        "The Tsunami", "Geography Lesson", "Glimpses of the Past",
        "Bepin Choudhury's Lapse of Memory", "The Last Bargain",
        "The Summit Within", "This is Jody's Fawn", "A Visit to Cambridge",
        "A Short Monsoon Diary", "On the Grasshopper and Cricket",
        "The Great Stone Face", "Macavity: The Mystery Cat",
        "Grammar: Reported Speech and Active-Passive", "Writing: Report and Story",
    ],
}

CHAPTERS["Hindi"] = {
    1: [  # Rimjhim 1
        "Jhoola", "Aam ki Kahani", "Aam ki Tokri", "Patte hi Patte", "Pakode",
        "Chhuk Chhuk Gaadi", "Rasoighar", "Chuhon ki Sabha", "Bandar aur Gilahri",
        "Pagdi", "Patang", "Gend-Balla", "Bandar Gaya Khet Mein", "Ek Buddhiya",
        "Main Bhi", "Lalu aur Peelu", "Chakai ke Chakdum",
        "Vyakaran: Varnamala", "Lekhan: Matra Abhyas",
    ],
    2: [  # Rimjhim 2
        "Oont Chala", "Bhalu ne Kheli Football", "Mhare Rakho Gopal",
        "Ek Din ki Baadshahat", "Bahut Hua", "Meri Kitab", "Titli aur Kali",
        "Bulbul", "Meethi Sarangi", "Tit-Tit-Tit", "Choti ka Kamaal", "Baaghban",
        "Straw se Kagaz", "Vyakaran: Sangya", "Lekhan: Vakya Rachna",
    ],
    3: [  # Rimjhim 3
        "Kakku", "Sikkon ka Safar", "Chand Wali Amma", "Man Karta Hai",
        "Bahadur Bitto", "Humse Sab Kehte", "Tip Tipwa", "Bandar Baant",
        "Akal Badi ya Bhains", "Kyonjimal aur Kaise Kaiselia",
        "Meera Behen aur Bagh", "Jab Mujhko Saanp ne Kaata", "Mirch ka Maza",
        "Sabse Achcha Ped", "Vyakaran: Sangya aur Sarvanam", "Lekhan: Anuchhed",
    ],
    4: [  # Rimjhim 4
        "Man ke Bhole-Bhale Baadal", "Jaisa Sawal Waisa Jawab", "Kirmich ki Gend",
        "Papa Jab Bachche The", "Dost ki Poshak", "Naav Banao Naav Banao",
        "Daan ka Hisab", "Kaun?", "Swatantrata ki Ore", "Thapp Roti Thapp Dal",
        "Padhakku ki Soojh", "Sunita ki Pahiya Kursi", "Hudhud", "Muft Hi Muft",
        "Vyakaran: Ling aur Vachan", "Lekhan: Patra Lekhan",
    ],
    5: [  # Rimjhim 5
        "Raakh ki Rassi", "Fasalon ke Tyohar", "Khilonewala", "Nanha Fankar",
        "Jahan Chah Wahan Raah", "Chitthi ka Safar", "Dakiye ki Kahani",
        "Ve Din Bhi Kya Din The", "Ek Maa ki Bebasi", "Ek Din ki Baadshahat",
        "Chawal ki Rotiyan", "Guru aur Chela", "Swami ki Dadi", "Bagh Aaya Us Raat",
        "Bishan ki Dileri", "Chhoti-si Hamari Nadi",
        "Vyakaran: Visheshan aur Kriya", "Lekhan: Nibandh",
    ],
    6: [  # Vasant 6
        "Vah Chidiya Jo", "Bachpan", "Nadaan Dost", "Chand se Thodi-si Gappe",
        "Aksharon ka Mahatva", "Paar Nazar Ke", "Saathi Haath Badhana",
        "Aise-Aise", "Ticket Album", "Jhansi ki Rani", "Jo Dekhkar Bhi Nahi Dekhte",
        "Sansar Pustak Hai", "Main Sabse Chhoti Houn", "Lokgeet", "Naukar",
        "Van ke Marg Mein", "Saans-Saans Mein Baans",
        "Vyakaran: Sangya, Sarvanam aur Visheshan", "Lekhan: Patra aur Anuchhed",
    ],
    7: [  # Vasant 7
        "Hum Panchhi Unmukt Gagan Ke", "Dadi Maa", "Himalaya ki Betiyan",
        "Kathputli", "Mithaiwala", "Rakt aur Hamara Sharir", "Papa Kho Gaye",
        "Shaam - Ek Kisan", "Chidiya ki Bacchi", "Apoorv Anubhav",
        "Rahim ke Dohe", "Kancha", "Ek Tinka",
        "Khanpan ki Badalti Tasveer", "Neelkanth", "Bhor aur Barkha",
        "Veer Kunwar Singh", "Vyakaran: Sandhi aur Muhavare", "Lekhan: Samvad",
    ],
    8: [  # Vasant 8
        "Dhwani", "Lakh ki Cheezein", "Bus ki Yatra", "Deewanon ki Hasti",
        "Chitthiyon ki Anoothi Duniya", "Bhagwan ke Dakiye",
        "Kya Nirash Hua Jaye", "Yah Sabse Kathin Samay Nahi",
        "Kabir ki Sakhiyan", "Kaamchor", "Jab Cinema ne Bolna Seekha",
        "Sudama Charit", "Jahan Pahiya Hai", "Akbari Lota", "Surdas ke Pad",
        "Pani ki Kahani", "Baaz aur Saanp",
        "Vyakaran: Samas aur Alankar", "Lekhan: Nibandh aur Vigyapan",
    ],
}

CHAPTERS["Mathematics"] = {
    1: [  # Math-Magic 1
        "Shapes and Space", "Numbers from One to Nine", "Addition", "Subtraction",
        "Numbers from Ten to Twenty", "Time", "Measurement",
        "Numbers from Twenty-one to Fifty", "Data Handling", "Patterns",
        "Numbers", "Money", "How Many", "Revision and Mental Maths",
    ],
    2: [  # Math-Magic 2
        "What is Long, What is Round?", "Counting in Groups", "How Much Can You Carry?",
        "Counting in Tens", "Patterns", "Footprints", "Jugs and Mugs", "Tens and Ones",
        "My Funday", "Add Our Points", "Lines and Lines", "Give and Take",
        "The Longest Step", "Birds Come, Birds Go", "How Many Ponytails?",
    ],
    3: [  # Math-Magic 3
        "Where to Look From", "Fun with Numbers", "Give and Take", "Long and Short",
        "Shapes and Designs", "Fun with Give and Take", "Time Goes On",
        "Who is Heavier?", "How Many Times?", "Play with Patterns", "Jugs and Mugs",
        "Can We Share?", "Smart Charts", "Rupees and Paise",
    ],
    4: [  # Math-Magic 4
        "Building with Bricks", "Long and Short", "A Trip to Bhopal", "Tick-Tick-Tick",
        "The Way The World Looks", "The Junk Seller", "Jugs and Mugs",
        "Carts and Wheels", "Halves and Quarters", "Play with Patterns",
        "Tables and Shares", "How Heavy? How Light?", "Fields and Fences",
        "Smart Charts",
    ],
    5: [  # Math-Magic 5
        "The Fish Tale", "Shapes and Angles", "How Many Squares?", "Parts and Wholes",
        "Does it Look the Same?", "Be My Multiple, I'll be Your Factor",
        "Can You See the Pattern?", "Mapping Your Way", "Boxes and Sketches",
        "Tenths and Hundredths", "Area and its Boundary", "Smart Charts",
        "Ways to Multiply and Divide", "How Big? How Heavy?",
    ],
    6: [
        "Knowing Our Numbers", "Whole Numbers", "Playing with Numbers",
        "Basic Geometrical Ideas", "Understanding Elementary Shapes", "Integers",
        "Fractions", "Decimals", "Data Handling", "Mensuration", "Algebra",
        "Ratio and Proportion", "Symmetry", "Practical Geometry",
    ],
    7: [
        "Integers", "Fractions and Decimals", "Data Handling", "Simple Equations",
        "Lines and Angles", "The Triangle and its Properties",
        "Comparing Quantities", "Rational Numbers", "Perimeter and Area",
        "Algebraic Expressions", "Exponents and Powers", "Symmetry",
        "Visualising Solid Shapes",
    ],
    8: [
        "Rational Numbers", "Linear Equations in One Variable",
        "Understanding Quadrilaterals", "Data Handling", "Squares and Square Roots",
        "Cubes and Cube Roots", "Comparing Quantities",
        "Algebraic Expressions and Identities", "Mensuration",
        "Exponents and Powers", "Direct and Inverse Proportions", "Factorisation",
        "Introduction to Graphs",
    ],
}

CHAPTERS["EVS"] = {
    1: [
        "Myself and My Body", "My Family", "My School", "The Food We Eat",
        "Plants Around Us", "Animals Around Us", "Water", "Air Around Us",
        "My House", "Clothes We Wear", "Keeping Clean", "Safety First",
        "Festivals We Celebrate", "Means of Transport",
    ],
    2: [
        "Parts of the Body and Sense Organs", "My Family and Neighbours",
        "Our Helpers", "Food for Health", "Plants: Parts and Uses",
        "Animals and Their Homes", "Birds Around Us", "Sources of Water",
        "Weather and Seasons", "Our Village and Our Town", "Good Habits",
        "Rules of the Road", "Our National Symbols", "Care of Pets",
    ],
    3: [  # Looking Around 3
        "Poonam's Day Out", "The Plant Fairy", "Water O' Water!", "Our First School",
        "Chhotu's House", "Foods We Eat", "Saying Without Speaking", "Flying High",
        "It's Raining", "What is Cooking", "From Here to There", "Work We Do",
        "Sharing Our Feelings", "The Story of Food", "Games We Play",
        "Here Comes a Letter", "A House Like This",
    ],
    4: [  # Looking Around 4
        "Going to School", "Ear to Ear", "A Day with Nandu", "The Story of Amrita",
        "Anita and the Honeybees", "Omana's Journey", "From the Window",
        "Reaching Grandmother's House", "Changing Families", "Hu Tu Tu, Hu Tu Tu",
        "The Valley of Flowers", "Changing Times", "A River's Tale", "Basva's Farm",
        "From Market to Home", "A Busy Month", "Nandita in Mumbai",
        "Too Much Water, Too Little Water",
    ],
}

CHAPTERS["Science"] = {
    5: [
        "Our Body and Its Systems", "Food and Health", "Plants: Growth and Reproduction",
        "Animals and Their Life", "Safety and First Aid", "Air, Water and Weather",
        "Rocks, Minerals and Soil", "The Solar System", "Force, Work and Energy",
        "Simple Machines", "Natural Disasters", "Keeping the Environment Clean",
    ],
    6: [
        "Food: Where Does It Come From?", "Components of Food", "Fibre to Fabric",
        "Sorting Materials into Groups", "Separation of Substances",
        "Changes Around Us", "Getting to Know Plants", "Body Movements",
        "The Living Organisms and Their Surroundings",
        "Motion and Measurement of Distances", "Light, Shadows and Reflections",
        "Electricity and Circuits", "Fun with Magnets", "Water", "Air Around Us",
        "Garbage In, Garbage Out",
    ],
    7: [
        "Nutrition in Plants", "Nutrition in Animals", "Fibre to Fabric", "Heat",
        "Acids, Bases and Salts", "Physical and Chemical Changes",
        "Weather, Climate and Adaptations", "Winds, Storms and Cyclones", "Soil",
        "Respiration in Organisms", "Transportation in Animals and Plants",
        "Reproduction in Plants", "Motion and Time",
        "Electric Current and its Effects", "Light", "Water: A Precious Resource",
        "Forests: Our Lifeline", "Wastewater Story",
    ],
    8: [
        "Crop Production and Management", "Microorganisms: Friend and Foe",
        "Synthetic Fibres and Plastics", "Materials: Metals and Non-Metals",
        "Coal and Petroleum", "Combustion and Flame",
        "Conservation of Plants and Animals", "Cell: Structure and Functions",
        "Reproduction in Animals", "Reaching the Age of Adolescence",
        "Force and Pressure", "Friction", "Sound",
        "Chemical Effects of Electric Current", "Some Natural Phenomena", "Light",
        "Stars and the Solar System", "Pollution of Air and Water",
    ],
}

CHAPTERS["Social Studies"] = {
    5: [
        "Our Earth and the Globe", "Maps and Map Reading", "Landforms of India",
        "Climate and Natural Vegetation", "Natural Resources", "Our Neighbours",
        "Means of Transport", "Means of Communication", "The Freedom Struggle",
        "Our Constitution", "Local Self-Government", "United We Stand",
    ],
    6: [
        "What, Where, How and When?", "On The Trail of the Earliest People",
        "From Gathering to Growing Food", "In the Earliest Cities",
        "Kingdoms, Kings and an Early Republic", "New Questions and Ideas",
        "Ashoka, the Emperor Who Gave Up War",
        "The Earth in the Solar System", "Globe: Latitudes and Longitudes",
        "Motions of the Earth", "Maps", "Major Domains of the Earth",
        "Understanding Diversity", "Diversity and Discrimination",
        "What is Government?", "Key Elements of a Democratic Government",
        "Panchayati Raj", "Rural and Urban Administration",
    ],
    7: [
        "Tracing Changes Through a Thousand Years", "New Kings and Kingdoms",
        "The Delhi Sultans", "The Mughal Empire", "Rulers and Buildings",
        "Towns, Traders and Craftspersons", "Devotional Paths to the Divine",
        "The Making of Regional Cultures", "Environment", "Inside Our Earth",
        "Our Changing Earth", "Air", "Water", "Natural Vegetation and Wildlife",
        "Human Environment: Settlement, Transport and Communication",
        "On Equality", "Role of the Government in Health",
        "How the State Government Works", "Understanding Media", "Markets Around Us",
    ],
    8: [
        "How, When and Where", "From Trade to Territory", "Ruling the Countryside",
        "Tribals, Dikus and the Vision of a Golden Age", "When People Rebel",
        "Civilising the Native, Educating the Nation",
        "Women, Caste and Reform", "The Making of the National Movement",
        "India After Independence", "Resources",
        "Land, Soil, Water, Natural Vegetation and Wildlife Resources",
        "Mineral and Power Resources", "Agriculture", "Industries",
        "Human Resources", "The Indian Constitution", "Understanding Secularism",
        "Why Do We Need a Parliament?", "Understanding Laws", "Judiciary",
        "Understanding Marginalisation", "Public Facilities",
    ],
}

CHAPTERS["Sanskrit"] = {
    5: [
        "Sanskrit Varnamala", "Shabd Parichayah", "Namaste Sanskritam",
        "Sankhya Gyanam", "Vachanam", "Ling Parichayah", "Sarvanam Parichayah",
        "Dhatu Parichayah", "Subhashitani", "Chitra Varnanam", "Sambhashanam",
    ],
    6: [  # Ruchira 1
        "Shabd Parichayah I", "Shabd Parichayah II", "Shabd Parichayah III",
        "Vidyalayah", "Vrikshah", "Samudratatah", "Bakasya Pratikarah",
        "Suktistabakah", "Kritagyata", "Sanskrit Sankhya", "Krishika Karmavira",
        "Dashamah Tvam Asi", "Vihasya Sharanam",
    ],
    7: [  # Ruchira 2
        "Subhashitani", "Durbuddhih Vinashyati", "Swavalambanam",
        "Hastini cha Vyaghrah cha", "Pandit Ramabai", "Sadachar",
        "Sankalpah Siddhidayakah", "Trivarnah Dhwajah", "Aham Sarvatra Khadami",
        "Vishwabandhutvam", "Samvadah", "Vyakaran: Shabdroop aur Dhaturoop",
    ],
    8: [  # Ruchira 3
        "Subhashitani", "Bilasya Vani na Kadapi me Shruta", "Digdarshanam",
        "Sadaiva Puratah Nidhehi Charanam", "Kanthasya Kamaniyata",
        "Gruham Shunyam Sutam Vina", "Bhartriharih", "Aham Sarvatra Khadami",
        "Sabha Shatakam", "Nirdhanah Dhanavan",
        "Vyakaran: Karak Prayog", "Vyakaran: Sandhi aur Samas",
    ],
}

CHAPTERS["Computer Science"] = {
    1: ["Meet the Computer", "Parts of a Computer", "Computers Around Us",
        "Starting and Shutting Down", "Using the Mouse", "Drawing in Paint",
        "The Keyboard", "Caring for the Computer"],
    2: ["The Computer: A Smart Machine", "Parts and What They Do", "The Keyboard",
        "Working with the Mouse", "Paint Tools", "Typing Words",
        "Files and Folders", "Computers at Work"],
    3: ["Computer Fundamentals", "Input and Output Devices", "The Windows Desktop",
        "MS Paint: Advanced Tools", "Introduction to Word Processing",
        "Typing Practice", "Storage Devices", "Safe Use of Computers"],
    4: ["Types of Computers", "Hardware and Software", "Working with Windows",
        "Word Processing: Formatting", "Introduction to the Internet",
        "Email Basics", "Digital Drawing", "Cyber Manners"],
    5: ["Computer Memory", "Operating Systems", "Word Processing: Tables and Pictures",
        "Introduction to Spreadsheets", "Presentations: The Basics",
        "The Internet and Browsers", "Algorithms and Flowcharts", "Being Safe Online"],
    6: ["Computer System and the Number System", "Windows Utilities",
        "Advanced Word Processing", "Spreadsheets: Formulas",
        "Presentations: Animation and Transitions", "Introduction to Scratch",
        "Internet Services", "Cyber Safety and Ethics"],
    7: ["Number System and Data Representation", "Networking Basics",
        "Spreadsheets: Functions and Charts", "Advanced Presentations",
        "Programming with Scratch", "Introduction to HTML", "Image Editing",
        "Digital Citizenship"],
    8: ["Computer Networks and the Internet", "HTML: Lists, Links and Images",
        "Introduction to Python", "Python: Variables and Data Types",
        "Spreadsheets: Data Analysis", "Database Basics",
        "Artificial Intelligence: A First Look", "Cyber Security and Ethics"],
}

CHAPTERS["Art & Craft"] = {
    1: ["Lines, Shapes and Doodles", "Colours Around Us", "Finger and Thumb Printing",
        "Drawing from Nature", "Paper Folding", "Clay Play", "Festival Craft",
        "Free Drawing and Display"],
    2: ["Drawing with Shapes", "Colour Mixing", "Leaf and Vegetable Printing",
        "Nature Drawing", "Paper Tearing and Pasting", "Clay Modelling",
        "Greeting Card Making", "Class Art Display"],
    3: ["Free-hand Drawing", "Shading and Colour Pencils", "Still Life: Simple Objects",
        "Landscape Drawing", "Origami", "Collage Work", "Poster Making",
        "Craft with Waste Material"],
    4: ["Perspective and Proportion", "Colour Theory", "Still Life: Groups of Objects",
        "Human Figure Sketching", "Print Making", "Clay Relief Work",
        "Poster and Slogan Design", "Portfolio and Exhibition"],
}

_PE_PRIMARY = [
    "Warm-up, Cool-down and Body Awareness", "Locomotor Skills",
    "Ball Skills: Throwing and Catching", "Balance and Coordination",
    "Simple Athletics: Running and Jumping", "Rhythmic and Movement Games",
    "Yoga: Basic Asanas and Breathing", "Team Games and Fair Play",
    "Health, Hygiene and Posture", "Annual Sports Preparation",
]
_PE_MIDDLE = [
    "Fitness Components and Testing", "Athletics: Track Events",
    "Athletics: Field Events", "Yoga: Asanas, Pranayama and Meditation",
    "Kho-Kho and Kabaddi", "Volleyball and Throwball", "Basketball",
    "Cricket and Football Skills", "Health, Nutrition and First Aid",
    "Rules, Officiating and Sportsmanship", "Annual Sports Meet Preparation",
]
CHAPTERS["Physical Education"] = {g: (_PE_PRIMARY if g <= 4 else _PE_MIDDLE)
                                  for g in range(1, 9)}
