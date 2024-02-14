# RobotsSSW
Programs and data for "Humans in charge of trading robots"

MelboR* are folders with data and programs for the first set of 4 experiments where participants were free to deploy chosen robots and could stop them at any time.
There are two main python programs that read the two main types of file:
- Files: Marketplace order/trading data (output15*.xls) and robot logs (r*robot.xls)
- Programs: PAspread_E*.py: python program that outputs b/a spreads and trading data; Probot_E*.py: python program that outputs robot use data (after merging trading data with robot logs)
- Please see notes files in some of the directories for rare (2) impurities in the data and how we addressed them
Output csv files: title should make clear what the content is; if not, see python programs.

Note that the "holdings" calculations in the output15*xls files are wrong. Use "Earnings.xlsx" for final earnings.

**************************************************

Utah* are the 9 sessions ran in the paper revision process. They are organized by coauthors from the University of Utah but the subjects are recruited by coauthers from Monash University. 

Session 1, 3, 9: No commitment, no panelty
Session 2, 4, 8: Commitment, no panelty
Session 5, 6, 7: Commitment, panelty

Files included in each folders are:
- Holdings_R*: initial and end holdings of each period per subject
- Orders_R8: orders happened in each period per subject
- Setup_Reupload*: holdings with cash updated by adding the random dividends of each period

*************************************************

The file "Profits (in cents) SNr 1-9.xlsx" contains the ex-ante & ex-post profits computed based on the realized dividends per period for the 9 Utah sessions. For any dividend information from the Utah sessions, please refer to this file.
