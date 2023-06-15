import AST
import copy
import sys

numbers=[]
operators=[]
varis=[]
constants={}
relops=[]
pos=0
lineNo=1
tok_id=-1
tok_im=-5
tok_num=-2
tok_x=-3
tok_y=-4
LParam=-6
RParam=-7
tok_op=-9
tok_end=-10
tok_equal=-11
tok_input=-12
Endl=-13
Sep=-14
tok_input=-15
tok_output=-16
tok_if=-17
tok_then=-18
tok_else=-19
tok_relop=-20
tok_and=-21
tok_bool=-22
def readInput(File):
	global pos,lineNo
	curChar=' '
	if(pos>0):
		pos-=1
	File.seek(pos)
	string=''
	# Skip White spaces and new lines
	while(curChar==" " or curChar=='\n' or curChar=='\t' or curChar=='\n'):
		if(curChar=='\n'):
			lineNo+=1
		curChar=File.read(1)
		pos+=1
	if(curChar.isalpha()):
		string+=curChar
		curChar=File.read(1)
		pos+=1
		while(curChar.isalnum()):
			string+=curChar
			curChar=File.read(1)
			pos+=1
		if(string=='x'):
			return tok_x
		elif(string=='y'):
			return tok_y
		elif(string=='im'):
			return tok_im
		elif(string=='end'):
			return tok_end
		elif(string=='input'):
			return tok_input
		elif(string=='output'):
			return tok_output
		elif(string=='if'):
			return tok_if
		elif(string=='then'):
			return tok_then
		elif(string=='else'):
			return tok_else
		elif(string=='and'):
			return tok_and
		elif(string=='bool'):
			return tok_bool
		else:
			varis.append(string)
			return tok_id
	elif(curChar.isdigit()):
		string+=curChar
		curChar=File.read(1)
		pos+=1
		while(curChar.isdigit() or curChar=='.'):
			string+=curChar
			curChar=File.read(1)
			pos+=1
		numbers.append(float(string))
		return tok_num
	elif(curChar=='('):
		pos+=1
		return LParam
	elif(curChar==')'):
		pos+=1
		return RParam
	elif(curChar=='+' or curChar=='-' or curChar=='*' or curChar=='/'):
		operators.append(curChar)
		pos+=1
		return tok_op
	elif(curChar==';'):
		pos+=1
		return Endl
	elif(curChar==','):
		pos+=1
		return Sep
	elif(curChar=='!'):
		pos+=1
		curChar = File.read(1)
		if(curChar=='='):
			pos+=1
			relops.append("!=")
			return tok_relop
		else:
			print(f"! hasto be followed by a =. Line Number {lineNo}")
			exit()
	elif(curChar=='='):
		pos+=1
		curChar = File.read(1)
		if(curChar=='='):
			pos+=1
			relops.append("==")
			return tok_relop
		else:
			operators.append('=')
			return tok_op
	elif(curChar=='>'):
		pos+=1
		curChar = File.read(1)
		if(curChar == '='):
			pos+=1
			relops.append(">=")
			return tok_relop
		else:
			relops.append(">")
			return tok_relop
	elif(curChar=='<'):
		pos+=1
		curChar = File.read(1)
		if(curChar == '='):
			pos+=1
			relops.append("<=")
			return tok_relop
		else:
			relops.append("<")
			return tok_relop
	elif(curChar==''):
		return 0
	else:
		print(f"invalid character {curChar} encountered in line number {lineNo}")
		exit()


def parser(File):
	global lineNo
	paramOpen=0
	imOpen=False
	astNode:AST.AST=None
	stageName:str=''
	chanNum=False
	coef=1
	coef_red=1
	coef_green=1
	coef_blue=1
	matchIf=False
	matchThen=False
	matchElse=False
	prevVar=''
	curVar=''
	Uminus=False
	stageDisc=False
	assignment=False
	isInput=False
	isOutput=False
	producer=''
	var=''
	lhs=''
	pos=''
	xPos=0
	yPos=0
	num=0
	curToken=readInput(File)
	while(curToken!=0):
		# print(f"current token is {curToken}")
		nextToken=readInput(File)
		# print(f"Next token is {nextToken}")
		if(curToken==tok_im):
			if(nextToken!=LParam):
				print(f"Wrong input after im in line number {lineNo}")
				exit()
			imOpen=True
			stageName=lhs
			astNode=AST.AST()
			astNode.setName(stageName)
			curToken=nextToken
		elif(curToken==tok_id):
			# print(varis,operators,numbers)
			var=varis.pop(-1)
			if(imOpen==True):
				if(nextToken==LParam):
					if var not in AST.head.keys() and var not in AST.inputStages:
						print(f"Compute stage {var} referenced before definition")
						exit()
					# stageDisc=True
					producer=var
					curToken=nextToken
				elif(nextToken==tok_op):
					if var not in constants.keys():
						print(f"Variable {var} referenced before assignment at line number {lineNo}")
						exit()
					coef=constants[var]
					if(Uminus==True):
						coef*=-1
						Uminus=False
					curToken=nextToken
				else:
					print(f"Wrong input after identifier {var} in line number {lineNo}")
			else:
				if(isInput==True):
					if(nextToken==Endl):
						AST.inputStages.append(var)
						isInput=False
						curToken=nextToken
					else:
						print(f"Wrong input after identifier {var} at line number {lineNo}")
						exit() 
				elif(isOutput==True):
					if(nextToken==Endl or nextToken==tok_op):
						if(AST.outputStage!=''):
							print(f"You can ony declare one output stage")
							exit()
						AST.outputStage=var;
						isOutput=False
						curToken=nextToken
					else:
						print(f"Wrong input after identifier {var} at line number {lineNo}")
						exit()
				else:
					if(nextToken==tok_op):
						curToken=nextToken
					elif(nextToken==Endl):
						if(var not in constants.keys()):
							print(f"Variable {var} referenced before assignment at line number {lineNo}")
							exit()
						num=constants[var]
					else:
						print(f"Wrong input after identifier {var} in line number {lineNo}")
						exit()
		elif(curToken==tok_op):
			# print(varis,operators,numbers)
			op=operators.pop(-1)
			if(imOpen==False):
				if(op!='='):
					print(f"We don't support expression evaluation right now")
					exit()
				if(nextToken!=tok_im and nextToken!=tok_id and nextToken!=tok_num):
					print(f"Wrong input after '=' at line number {lineNo}")
					exit()
				lhs=var
				assignment=True
				curToken=nextToken
			else:
				if(stageDisc==True):
					if(op=='-'):
						if(nextToken!=tok_num):
							print(f"Wrong input after {op} at line number {lineNo}")
							exit()
						Uminus=True
						curToken=nextToken
					elif(op=='+'):
						if(nextToken!=tok_num):
							print(f"Wrong input after {op} at line number {lineNo}")
							exit()
						Uminus=False
						curToken=nextToken
					else:
						print(f"wrong operator {op} at line number {lineNo}")
						exit()
				else:
					if(op=='-'):
						if(nextToken!=tok_num and nextToken!=tok_id):
							print(f"wrong input after {op} at line number {lineNo}")
							exit()
						if(producer==''):
							astNode.addConstant(coef)
						Uminus=True
						curToken=nextToken
					elif(op=='+'):
						if(nextToken!=tok_num and nextToken!=tok_id):
							print(f"wrong input after {op} at line number {lineNo}")
							exit()
						if(producer==''):
							astNode.addConstant(coef)
						Uminus=False
						curToken=nextToken
					elif(op=='*'):
						if(nextToken!=tok_id):
							print(f"wrong input after {op} at line number {lineNo}")
							exit()
						# producer=var
						curToken=nextToken
					else:
						print(f"Wrong operator at line number {lineNo}")
						exit()   
		elif(curToken==tok_num):
			# print(varis,operators,numbers)
			num=numbers.pop(-1)
			if(imOpen==True and matchIf==False):
				if(stageDisc==True):
					if(Uminus==True):
						num*=-1
						Uminus=False
					if(num!=int(num)):
						print(f"Stencil coordinates and channel numbers have to be an integer. Line number {lineNo}")
						exit()
					if(pos=='x'):
						xPos=int(num)
					elif(pos=='y'):
						yPos=int(num)
					elif(chanNum==True):
						if num==0:
							coef_red = coef
						elif num==1:
							coef_green = coef
						elif num==2:
							coef_blue = coef
						else:
							print(f"You cannot index a channel with a number greater than 2. Line Number {lineNo}")
							exit()
					else:
						print("This part of the code is not reachable.")
						exit()
					if(nextToken==RParam or nextToken==Sep):
						curToken=nextToken
					else:
						print(f"Wrong input after the number {num}, at line number {lineNo}")
						exit()
				else:
					coef=num
					if(Uminus==True):
						coef*=-1
						Uminus=False
					if(nextToken==tok_op):
						curToken=nextToken
					else:
						print(f"Wrong input after the number {coef} in line number {lineNo}")
						exit()   
			elif(imOpen==True and matchIf==True):
				pass
			else:
				if(Uminus==True):
					num*=-1
					Uminus=False
				if(nextToken==Endl):
					curToken=nextToken
				else:
					print(f"Wrong input after the number {coef} in line number {lineNo}")
		elif(curToken==tok_x):
			if(imOpen==False):
				print(f"x is a reserved identifier. Line number {lineNo}")
				exit()
			if(stageDisc==False and stageName!=var):
				print(f"x is a reserved identifier. Line number {lineNo}")
				exit()
			pos='x'
			if(nextToken==Sep or nextToken==tok_op):
				curToken=nextToken
			else:
				print(f"Wrong input after x in line number {lineNo}")
				exit()
		elif(curToken==tok_y):
			if(imOpen==False):
				print(f"y is a reserved identifier. Line number {lineNo}")
				exit()
			if(stageDisc==False and stageName!=var):
				print(f"y is a reserved identifier. Line number {lineNo}")
				exit()
			pos='y'
			if(nextToken==RParam or nextToken==tok_op or nextToken==Sep):
				curToken=nextToken
			else:
				print(f"Wrong input after y in line number {lineNo}")
				exit()
		elif(curToken==LParam):
			if(imOpen==False):
				print(f"We don't support expression evaluation at this point")
				exit()
			if(stageDisc==True):
				print(f"Previously opened bracket is not yet closed")
				exit()
			if(nextToken==tok_x):
				stageDisc=True
				paramOpen+=1
				curToken=nextToken
			else:
				print(f"Wrong input after '(' in line number {lineNo}")
				exit()
		elif(curToken==RParam):
			if(paramOpen==0):
				print(f"You are trying to close set of parenthesis you never opened, on line number {lineNo}")
				exit()
			paramOpen-=1
			if(stageDisc==True):
				if(var!=stageName):
					if coef_red==coef_green==coef_blue==1:
						coef_blue=coef_green=coef_red=coef
					astNode.buildCoefficient(producer,xPos,yPos,[coef_red,coef_green,coef_blue])
					coef=1
					coef_red=1
					coef_green=1
					coef_blue=1
					xPos=0
					yPos=0
				stageDisc=False
				chanNum=False
				producer=''
			if(nextToken!=tok_end and nextToken!=tok_op and nextToken!=tok_id and nextToken!=tok_num):
				print(f"Wrong input after ')' in line number {lineNo}")
				exit()
			curToken=nextToken
		elif(curToken==tok_end):
			if(imOpen==False):
				print(f"Invalid use of keyword 'end' in line number {lineNo}")
				exit()
			if(matchIf==True):
				if matchThen==False:
					print(f"if condition has to be followed by a then statement. Line number {lineNo}")
					exit()
				matchIf=False
				matchElse=False
				matchThen=False
				# TODO implement rest of the if statement.
			else:
				astNode.checkShape()
				# astNode.removePointless(AST.head,AST.inputStages)
				AST.head[stageName]=copy.deepcopy(astNode)
				astNode=None
				lhs=''
				imOpen=False
				stageDisc=False
				assignment=False
				var=False
				xPos=0
				yPos=0
				producer=''
				stageName=''
				num=0
				coef=1
			if(nextToken!=tok_id and nextToken!=tok_output and nextToken!=0):
				print(f"Wrong input after 'end' at line number {lineNo}")
				exit()
			curToken=nextToken
		elif(curToken==Sep):
			if(stageDisc==False):
				print(f"A \',\' does not belong at line number {lineNo}")
				exit()
			if(nextToken==tok_num):
				if pos=='y':
					chanNum=True
					pos=''
			elif(nextToken!=tok_y):
				print(f"Wrong input after \',\' at line number {lineNo}")
				exit()
			curToken=nextToken
		elif(curToken==Endl):
			if(imOpen==True):
				print(f"This ';' does not belong here at line number {lineNo}")
				exit()
			if(nextToken!=tok_id and nextToken!=tok_input and nextToken!=tok_output and nextToken!=0):
				print(f"Wrong input after ';' at line number {lineNo}")
				exit()
			if(assignment==True):
				constants[lhs]=num
				assignment=False
			curToken=nextToken
		elif(curToken==tok_input):
			if(nextToken!=tok_id):
				print(f"Wrong input after keyword 'input' at line number {lineNo}")
				exit()
			isInput=True
			curToken=nextToken
		elif(curToken==tok_output):
			if(nextToken!=tok_id):
				print(f"Wrong input after the keyword 'output' at line number {lineNo}")
				exit()
			if(imOpen==True or stageDisc==True):
				print(f"Improper use of the keywork 'output' at line number {lineNo}")
				exit()
			isOutput=True
			curToken=nextToken
		elif(curToken==tok_if):
			if(imOpen==True):
				if matchIf:
					print(f"This compiler currently doesn\'t support nested conditional statements")
					exit()
				matchIf = True
				if nextToken==tok_id:
					astNode.setType('if')
					curToken=nextToken
				else:
					print(f"invalid token after the if statement at line number {lineNo}")
					exit()
			else:
				print(f"We currently don't support if statements outside the image block.")
				exit()
		elif(curToken==tok_then):
			if(imOpen==True):
				if matchIf:
					if nextToken==tok_num:
						curToken=nextToken
					else:
						print(f"invalid token after the then keyword at line number {lineNo}")
						exit()
				else: 
					print(f"Improper use of the then keyword at line number {lineNo}")
					exit()
			else:
				print(f"We currently don't support if statements outside the image block.")
				exit()
		elif(curToken==tok_else):
			if(imOpen==True):
				if matchIf:
					if nextToken==tok_num:
						curToken=nextToken
					else:
						print(f"invalid token after the else keyword at line number {lineNo}")
						exit()
				else: 
					print(f"Improper use of the then keyword at line number {lineNo}")
					exit()
			else:
				print(f"We currently don't support if statements outside the image block.")
				exit()
		elif(curToken==tok_relop):
			if(imOpen==True):
				pass
			else:
				print(f"We currently don't support relational operators outside the image block.")
				exit()
		else:
			pass


if __name__=="__main__":
	File=open(sys.argv[1],'r')
	# print(File.tell())
	parser(File)
	for node in AST.head.keys():
		print("-----------------------------------------------------------")
		print(f"Node: {node}")
		print(f"Producers: {AST.head[node].producers}")
		print(f"Coefs: {AST.head[node].coefficient}")
