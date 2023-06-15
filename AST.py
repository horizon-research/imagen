class AST:
	def __init__(self) -> None:
		self.name=''
		self.producers=[]
		self.coefficient={}
		self.constant=0
		self.type=''
		self.relop=''
		self.if_node = None
		self.relop_nodes = []
		self.boolPairs=[]
	
	def setType(self,type):
		if self.type!='':
			print(f"AST type already set cannot use any other type of statement in this block.")
			exit()
		self.type=type
	
	def addConstant(self,constant):
		self.constant+=constant
	
	def setName(self,name) -> None:
		self.name=name
	
	def buildCoefficient(self,producer,xPos,yPos,coefficient) -> None:
		# print(f"Before: {self.coefficient}")
		if producer not in self.coefficient.keys():
			self.coefficient[producer]={}
			self.producers.append(producer)
		if xPos not in self.coefficient[producer].keys():
			self.coefficient[producer][xPos]={}
		if yPos in self.coefficient[producer][xPos]:
			self.coefficient[producer][xPos][yPos][0]+=coefficient[0]
			self.coefficient[producer][xPos][yPos][1]+=coefficient[1]
			self.coefficient[producer][xPos][yPos][2]+=coefficient[2]
		else:
			self.coefficient[producer][xPos][yPos]=coefficient
	
	def checkShape(self) -> None:
		for producer in self.producers:
			Xs=list(self.coefficient[producer].keys())
			if(0 not in Xs):
				print(f"This stencil is not balanced. You are not doing any operations for {producer} at position (x,y)")
				exit()
			xMin=abs(min(Xs))
			xMax=max(Xs)
			if(abs(xMax-xMin)>1):
				print(f"stencil for consumer {self.name} and producer {producer} is not balanced")
				exit()
			if(len(Xs)==1):
				continue
			for x in Xs[1:]:
				if(self.coefficient[producer][x].keys()!=self.coefficient[producer][Xs[0]].keys()):
					print("your stencil is not rectangular.")
					exit()
			Ys=list(self.coefficient[producer][Xs[0]].keys())
			if 0 not in Ys:
				print(f"This stencil is not balanced. You are not doing any operations for {producer} at position (x,y)")
				exit()
			yMin=abs(min(Ys))
			yMax=max(Ys)
			if(abs(yMax-yMin)>1):
				print(f"stencil for consumer {self.name} and producer {producer} is not balaned")
				exit()
	
	def findPointless(self,producer) -> bool:
		isPointless=False
		if(len(producer.producers)>1):
			return isPointless
		pProd=producer.producers[0]
		if(len(producer.coefficient[pProd].keys())>1):
			return isPointless
		x=list(producer.coefficient[pProd].keys())[0]
		if(len(producer.coefficient[pProd][x].keys())>1):
			return isPointless
		return True
	
	def removePointless(self,head,inputs) -> None:
		# coefs={}
		notProducer=[]
		for producer in self.producers:
			if(producer in inputs):
				continue
			if(len(self.coefficient[producer].keys())>1):
				continue
			x=list(self.coefficient[producer].keys())[0]
			if(len(self.coefficient[producer][x].keys())>1):
				continue
			isPointless=self.findPointless(head[producer])
			if(isPointless==True):
				notProducer.append(producer)
				producerNode=head[producer]
				parentProducer=producerNode.producers[0]
				coef=producerNode.coefficient[parentProducer]
				if parentProducer not in self.producers:
					self.producers.append(parentProducer)
					self.coefficient[parentProducer]=coef
				else:
					for xPos in coef.keys():
						if xPos not in self.coefficient[parentProducer].keys():
							self.coefficient[parentProducer][xPos]=coef[xPos]
							continue
						for yPos in coef[xPos].keys():
							if yPos not in self.coefficient[parentProducer][xPos].keys():
								self.coefficient[parentProducer][xPos][yPos]=coef[xPos][yPos]
								continue
							# print(self.coefficient[parentProducer][xPos][yPos],coef[xPos][yPos])
							self.coefficient[parentProducer][xPos][yPos][0]+=coef[xPos][yPos][0]
							self.coefficient[parentProducer][xPos][yPos][1]+=coef[xPos][yPos][1]
							self.coefficient[parentProducer][xPos][yPos][2]+=coef[xPos][yPos][2]
				# sorting the dict and making it rectangular
				self.coefficient[parentProducer]=dict(sorted(self.coefficient[parentProducer].items()))
				for x in self.coefficient[parentProducer].keys():
					self.coefficient[parentProducer][x]=dict(sorted(self.coefficient[parentProducer][x].items()))
				for x in self.coefficient[parentProducer].keys():
					for y in self.coefficient[parentProducer][0].keys():
						if y not in self.coefficient[parentProducer][x].keys():
							self.coefficient[parentProducer][x][y]=0     
		for np in notProducer:
			self.producers.remove(np)
			self.coefficient.pop(np)
		for producer in self.producers:
			self.coefficient[producer]=dict(sorted(self.coefficient[producer].items()))
			for x in self.coefficient[producer].keys():
				self.coefficient[producer][x]=dict(sorted(self.coefficient[producer][x].items()))

class RelOp:
	def __init__(self,op:str,lhs:str,rhs:str) -> None:
		self.op = op
		self.lhs = lhs
		self.rhs = rhs
	
class IfStm:
	def __init__(self,cond,then_val,else_val) -> None:
		self.cond = cond
		self.then_val = then_val
		self.else_val = else_val

# * Definitions
head={}
inputStages=[]
outputStage=''