from pprint import pprint

import AST
import front_end
import numpy as np
import sys
from copy import deepcopy

def cleanAST():
	producers=[]
	for stage in AST.head.keys():
		node=AST.head[stage]
		producers.extend(x for x in node.producers if x not in producers)
	toRemove=[]
	toRemove.extend(x for x in AST.head.keys() if x not in producers and x!=AST.outputStage)
	for x in toRemove:
		AST.head.pop(x)


# * calculate pad around the image and store them as tuple (top,bottom,left,right)
def calculatePad(stencils:dict):
	pad={}
	for producer in stencils.keys():
		pad[producer]={}
		for consumer in stencils[producer].keys():
			sw=stencils[producer][consumer][0]
			if sw%2==0:
				left=int((sw-2)/2)
				right=int(sw/2)
			else:
				left=right=int((sw-1)/2)
			sh=stencils[producer][consumer][1]
			if sh%2==0:
				top=int(sh/2)
				bottom=int((sh-2)/2)
			else:
				top=bottom=int((sh-1)/2)
			pad[producer][consumer]=(top,bottom,left,right)
	return pad  


# * Get depenency graph from the AST
def genDependency(width:int):
	dependency={}
	stencils={}
	A={}
	C={}
	for stage in AST.inputStages:
		dependency[stage]={}
		stencils[stage]={}
		A[stage]=[]
		C[stage]=[]
	for stage in AST.head.keys():
		node:AST.AST=AST.head[stage]
		# print(node.coefficient)
		for producer in node.coefficient.keys():
			SW=len(node.coefficient[producer].keys())
			SH=len(node.coefficient[producer][0].keys())
			stencils[producer][stage]=(SW,SH)   #width, height
			# dep=(SH-1)*width
			# dependency[producer][stage]=dep+1
		A[stage]=[]
		C[stage]=[]
		if(stage!=AST.outputStage):
			stencils[stage]={}
			# dependency[stage]={}
	pad = calculatePad(stencils)
	for stage in AST.head.keys():
		node:AST.AST=AST.head[stage]
		for producer in node.coefficient.keys():
			SW=len(node.coefficient[producer].keys())
			SH=len(node.coefficient[producer][0].keys())
			# stencils[producer][stage]=(SW,SH)
			dep=(SH-1-pad[producer][stage][0])*width
			dependency[producer][stage]=dep+1
		if(stage!=AST.outputStage):
			dependency[stage]={}
	return A,C,dependency,stencils,pad

""" Split into virtual stages """
def combineLines(stencils:dict,dependency:dict,pad:dict,width:int,A:dict,C:dict):
	virtStage = {}
	# virt_stages = []
	newStencils = {}
	newDep = {}
	newPad = {}
	prods = list(dependency.keys())
	for producer in prods:
		sf = 1  #* tells which virt stage starts first.
		cons = list(dependency[producer].keys())
		newProducer = producer
		if producer in virtStage.keys():
			newProducer = virtStage[producer][0]
		newStencils[newProducer] = {}
		newDep[newProducer] = {}
		newPad[newProducer] = {}
		for consumer in cons:
			sf = 1 if pad[producer][consumer][0]%2==1 else 2
			sfc = 2 if sf==1 else 1
			if consumer in virtStage.keys():
				csf = virtStage[consumer][0]
				csfc = virtStage[consumer][1]
				if stencils[producer][consumer][1]>1:
					temp = stencils[producer][consumer]
					newStencils[newProducer][consumer+"_1"] = (temp[0],int((temp[1]+1)/2)) if temp[1]%2==1 else (temp[0],int(temp[1]/2))
					newStencils[newProducer][consumer+"_2"] = (temp[0],int((temp[1]-1)/2)) if temp[1]%2==1 else (temp[0],int(temp[1]/2))
					temp = dependency[producer][consumer]
					newDep[newProducer][consumer+"_1"] = (newStencils[newProducer][consumer+"_1"][1]-1)*width + 1
					newDep[newProducer][consumer+"_2"] = (newStencils[newProducer][consumer+"_2"][1]-1)*width + 1
					temp = pad[producer][consumer]
					pad_top_1 = int((temp[0]+1)/2) if temp[0]%2!=0 else int(temp[0]/2)
					pad_top_2 = int((temp[0]-1)/2) if temp[0]%2!=0 else int(temp[0]/2)
					pad_bot_1 = int((temp[1]+1)/2) if temp[1]%2!=0 else int(temp[1]/2)
					pad_bot_2 = int((temp[1]-1)/2) if temp[1]%2!=0 else int(temp[1]/2)
					newPad[newProducer][consumer+"_1"] = (pad_top_1,pad_bot_1,temp[2],temp[3])
					newPad[newProducer][consumer+"_2"] = (pad_top_2,pad_bot_2,temp[2],temp[3])
				else:
					temp = stencils[producer][consumer]
					newStencils[newProducer][csf] = (temp[0],int((temp[1]+1)/2)) if temp[1]%2==1 else (temp[0],int(temp[1]/2))
					newStencils[newProducer][csfc] = (temp[0],int((temp[1]-1)/2)) if temp[1]%2==1 else (temp[0],int(temp[1]/2))
					temp = dependency[producer][consumer]
					newDep[newProducer][csf] = (newStencils[newProducer][consumer+f"_{sf}"][1]-1)*width + 1
					newDep[newProducer][csfc] = (newStencils[newProducer][consumer+f"_{sfc}"][1]-1)*width + 1
					temp = pad[producer][consumer]
					pad_top_1 = int((temp[0]+1)/2) if temp[0]%2!=0 else int(temp[0]/2)
					pad_top_2 = int((temp[0]-1)/2) if temp[0]%2!=0 else int(temp[0]/2)
					pad_bot_1 = int((temp[1]+1)/2) if temp[1]%2!=0 else int(temp[1]/2)
					pad_bot_2 = int((temp[1]-1)/2) if temp[1]%2!=0 else int(temp[1]/2)
					newPad[newProducer][csf] = (pad_top_1,pad_bot_1,temp[2],temp[3])
					newPad[newProducer][csfc] = (pad_top_2,pad_bot_2,temp[2],temp[3])
			else:
				if stencils[producer][consumer][1]>1:
					virtStage[consumer] = (consumer+f"_{sf}",consumer+f"_{sfc}")
					A.pop(consumer)
					C.pop(consumer)
					A[virtStage[consumer][0]] = []
					A[virtStage[consumer][1]] = []
					C[virtStage[consumer][0]] = []
					C[virtStage[consumer][1]] = []
					temp = stencils[producer][consumer]
					newStencils[newProducer][consumer+"_1"] = (temp[0],int((temp[1]+1)/2)) if temp[1]%2==1 else (temp[0],int(temp[1]/2))
					newStencils[newProducer][consumer+"_2"] = (temp[0],int((temp[1]-1)/2)) if temp[1]%2==1 else (temp[0],int(temp[1]/2))
					temp = dependency[producer][consumer]
					newDep[newProducer][consumer+"_1"] = (newStencils[newProducer][consumer+"_1"][1]-1)*width + 1
					newDep[newProducer][consumer+"_2"] = (newStencils[newProducer][consumer+"_2"][1]-1)*width + 1
					temp = pad[producer][consumer]
					pad_top_1 = int((temp[0]+1)/2) if temp[0]%2!=0 else int(temp[0]/2)
					pad_top_2 = int((temp[0]-1)/2) if temp[0]%2!=0 else int(temp[0]/2)
					pad_bot_1 = int((temp[1]+1)/2) if temp[1]%2!=0 else int(temp[1]/2)
					pad_bot_2 = int((temp[1]-1)/2) if temp[1]%2!=0 else int(temp[1]/2)
					# print(f"modifying pad for {temp}")
					# print(pad_top_1,pad_bot_1,temp[2],temp[3])
					newPad[newProducer][consumer+"_1"] = (pad_top_1,pad_bot_1,temp[2],temp[3])
					newPad[newProducer][consumer+"_2"] = (pad_top_2,pad_bot_2,temp[2],temp[3])
				else:
					newStencils[newProducer][consumer] = stencils[producer][consumer]
					newDep[newProducer][consumer] = dependency[producer][consumer]
					newPad[newProducer][consumer] = pad[producer][consumer]
			sf = sfc
		if producer in virtStage.keys():
			newStencils[virtStage[producer][1]] = newStencils[virtStage[producer][0]]
			newDep[virtStage[producer][1]] = newDep[virtStage[producer][0]]
			newPad[virtStage[producer][1]] = newPad[virtStage[producer][0]]
	return newStencils,newDep,newPad,virtStage


def findAllPaths(start,end,graph,path=[]):
	""" Find all paths between two nodes """
	path = path + [start]
	if(start == end):
		return [path]
	if(start not in graph.keys()):
		return []
	paths = []
	for node in graph[start].keys():
		if(node not in path):
			newpaths=findAllPaths(node,end,graph,path)
			for newpath in newpaths:
				paths.append(newpath)
	return paths


def genLevel(dependency,producer):   #TODO: This is mostly correct. Now, use actual distance. 
	""" Generate access levels  """
	levels={}
	levels[0]=[producer]
	for i in dependency[producer].keys():
		paths=findAllPaths(producer,i,dependency)
		maxLen=0
		for path in paths:
			pathLength=len(path)-1
			if(pathLength>maxLen):
				maxLen=pathLength
		if(maxLen not in levels.keys()):
			levels[maxLen]=[]
		levels[maxLen].append(i)
	nLevels={}
	# lkeys = list(levels.keys()).sort()
	pl=0
	for lvl in levels.keys():
		# print(levels)
		if lvl==0:
			nLevels[lvl] = levels[lvl]
			continue
		nLevels[pl+1] = levels[lvl]
		pl+=1
	# print('============================')
	# pprint(nLevels)
	# pprint(levels)
	# print('============================')
	return nLevels

def modifyLevels(dependency:dict,accessLevels:dict,virtStage:dict,producer):
	# if producer not in accessLevels.keys():
	# 	return
	# print(f"Modifying access levels for {producer}")
	# print(virtStage)
	# print(accessLevels)
	key_list = list(accessLevels.keys())
	val_list = list(accessLevels.values())
	done = []
	for consumer in dependency[producer].keys():
		consumer=consumer[:-2]
		if consumer not in virtStage.keys() or consumer in done: 
			continue
		done.append(consumer)
		lev_1 = 0
		lev1 = []
		lev_2 = 0
		lev2 = []
		# print(virtStage[consumer])
		for i in range(len(val_list)):
			if virtStage[consumer][0] in val_list[i]:
				lev_1 = key_list[i]
				lev1 = val_list[i]
			if virtStage[consumer][1] in val_list[i]:
				lev_2 = key_list[i]
				lev2 = val_list[i]
		# print(lev_1,lev_2)
		if lev_1>lev_2:
			accessLevels[lev_1] = lev2
			accessLevels[lev_2] = lev1
	# print(accessLevels)

def countPointwise(levels,dependency,stencils,Lk,Lkt,producer,consumer):
	indexKT=list(levels.keys()).index(Lkt)
	indexK=list(levels.keys()).index(Lk)
	count=0
	toRemove=[]
	while count<=stencils[producer][consumer][0]-1:
		indexKT-=1
		if(indexKT<=indexK):
			return count,toRemove
		curLevel=list(levels.keys())[indexKT]
		# curConsumer=levels[curLevel]
		if(Lkt-list(levels.keys())[indexKT]>stencils[producer][consumer][0]-1):
			# readRegs[producer][consumer]=toRemove
			return count,toRemove
		for curConsumer in levels[curLevel]:
			if stencils[producer][curConsumer][0]>1 or stencils[producer][curConsumer][1]>1:
				# readRegs[producer][consumer]=toRemove
				return count,toRemove
		curConsumer=levels[curLevel][0]
		paths=findAllPaths(curConsumer,consumer,dependency)
		maxDep=1
		if len(paths)>0:
			for path in paths:
				dep=0
				for i in range(1,len(path)):
					dep+=dependency[path[i-1]][path[i]]
				if dep>maxDep:
					maxDep=dep
		if maxDep>Lkt-curLevel:
			# readRegs[producer][consumer]=toRemove
			return count,toRemove
		count+=1
		toRemove.append(curLevel)


def maxStencil(Levels,stencils,level):
	producer=Levels[0][0]
	maxSW=0
	maxConsumer=""
	for consumers in Levels[level]:
		sw=stencils[producer][consumers][0]
		if sw>maxSW:
			maxSW=sw
			maxConsumer=consumers
	return maxSW,maxConsumer

def optimisePointwise(Levels,dependency,stencils,readRegs):
	producer=Levels[0][0]
	lks=list(Levels.keys())
	Lk=0
	i=len(lks)-1
	newLevels={}
	toRemove=[]
	while(i>0):
		Lkt=lks[i]
		SW,consumer=maxStencil(Levels,stencils,Lkt)
		if(stencils[producer][consumer][0]>1 and Lkt not in toRemove):
			count,temp=countPointwise(Levels,dependency,stencils,Lk,Lkt,producer,consumer)
			toRemove.extend(x for x in temp if x not in toRemove)
			if(len(toRemove)>0):
				if(producer not in readRegs.keys()):
					readRegs[producer]={}
				readRegs[producer][consumer]=[]
				for rem in toRemove:
					readRegs[producer][consumer].extend(x for x in Levels[rem] if x not in readRegs[producer][consumer])
					# readRegs[producer][consumer].append(Levels[rem])
			newLkt=Lkt-count
			newLevels[newLkt]=Levels[Lkt]
		elif(Lkt not in toRemove):
			newLevels[Lkt]=Levels[Lkt]
		else:
			pass
		i-=1
		if i==0:
			newLevels[0]=Levels[0]
			break
	return newLevels,readRegs

def hasStencilConsumers(producer,stencils,dependency,threshold=50):
	for key in stencils[producer].keys():
		if stencils[producer][key][1]>1:
			print(producer,key)
			return True
		paths=findAllPaths(producer,key,dependency)
		maxLen=0
		for path in paths:
			curLen=0
			path.remove(producer)
			prev_i = producer
			for i in path:
				curLen+=dependency[prev_i][i]
				prev_i = i
			if curLen>maxLen:
				maxLen=curLen
		if maxLen>threshold:
			return True
	return False           

def augmentLevels(levels:dict,stencils:dict):
	producer=levels[0][0]
	lvs=sorted(list(levels.keys()))
	newLevels={}
	toIncrease=0
	# print(f"augmentLevels {levels}")
	for level in lvs:
		if(level==0):
			newLevels[level]=levels[level]
			continue
		if(len(levels[level])==1):
			newLevels[level+toIncrease]=levels[level]
			continue
		SHS={}
		for consumer in levels[level]:
			if stencils[producer][consumer][1] not in SHS.keys():
				SHS[stencils[producer][consumer][1]]=[]
			SHS[stencils[producer][consumer][1]].append(consumer)
		if(len(SHS.keys())==1):
			newLevels[level+toIncrease]=levels[level]
			continue
		# print(SHS.keys())
		# print(SHS.items())
		# print(f"hallo {SHS}")
		SHS=dict(sorted(SHS.items(),reverse=True))
		for i in range(len(SHS.keys())):
			newLevels[level+toIncrease+i]=SHS[list(SHS.keys())[i]]
		toIncrease+=len(SHS.keys())-1
	# print(f"after augmentLevels {newLevels}")
	return newLevels

def findRedirection(levels,stencils,readRegs,producer,virtStage={}):
	for lv in levels.keys():
		if lv==0 or len(levels[lv])==1:
			continue
		indirection = []
		for i in range(len(levels[lv])-1):
			consumer = levels[lv][i]
			if producer in readRegs.keys() and consumer in readRegs[producer].keys():
				continue
			for j in range(i+1,len(levels[lv])):
				nextConsumer = levels[lv][j]
				# print(f"Consumer {consumer} nextConsumer {nextConsumer}")
				if nextConsumer[-2:]=="_1" or nextConsumer[-2:]=="_2":
					oldNextConsumer = nextConsumer[:-2]
					if consumer in virtStage[oldNextConsumer]:
						continue
					c1 = virtStage[oldNextConsumer][0]
					c2 = virtStage[oldNextConsumer][1]
					if c1 in indirection or c2 in indirection:
						continue
					pass
				if nextConsumer in indirection:
					continue
				if stencils[producer][consumer][1]==stencils[producer][nextConsumer][1] and stencils[producer][consumer][0]==stencils[producer][nextConsumer][0]:
					if producer not in readRegs.keys():
						readRegs[producer]={}
					if nextConsumer not in readRegs[producer].keys():
						readRegs[producer][nextConsumer] = consumer
					indirection.append(nextConsumer)
		for stages in indirection:
			levels[lv].remove(stages)	

def genHardwareConstraints(dependency:dict,stencils:dict,pad:dict,sram:int,A:dict,B:list,width:int,readRegs:dict,combine=False,virtStage={}):
	accessLevels={}
	for producer in dependency.keys():
		if(hasStencilConsumers(producer,stencils,dependency)==False):
			continue
		levels=genLevel(dependency,producer)
		# print(f"After generating levels {levels}, {dependency}")
		levels,readRegs=optimisePointwise(levels,dependency,stencils,readRegs)
		levels=augmentLevels(levels,stencils)
		findRedirection(levels,stencils,readRegs,producer,virtStage=virtStage)
		# print(f"Before {levels}")
		if(combine):
			# print("==============gen HW cons with combine===========")
			# print(virtStage)
			modifyLevels(dependency,levels,virtStage,producer)
		# print(f"After {levels}")
		# findRedirection(levels,stencils,readRegs,producer,combine)
		accessLevels[producer]=levels
		# print(levels)
		lks=sorted(list(levels.keys()))
		for i in range(0,len(lks)-1):
			for j in range(1,len(lks)):
				t=lks[j]-lks[i]
				# print(t,sram,levels[lks[j]],levels[lks[i]])
				if t >= sram:
					for var in A.keys():
						if(var==levels[lks[i]][0]):
							A[var].append(-1)
						elif(var==levels[lks[j]][0]):
							A[var].append(1)
						else:
							A[var].append(0)
					# print(f"Producer {producer} consumer {levels[lks[j]][0]}")
					# pprint(stencils)
					# pprint(pad)
					temp=-stencils[producer][levels[lks[j]][0]][1] + pad[producer][levels[lks[j]][0]][0]  #-2*0.999  #-1 #+sram-t
					temp=temp*width
					B.append(temp)
	return accessLevels


def genCausalityConstraints(dependency:dict,A:dict,B:list,C:dict):
	for producer in dependency.keys():
		toKeep=''
		objLen=0
		for consumer in dependency[producer].keys():
			for key in A.keys():
				if(key==producer):
					# print(f"Producer is {key}")
					A[key].append(-1)
				elif(key==consumer):
					# print(f"Consumer is {key}")
					A[key].append(1)
				else:
					A[key].append(0)
			toAppend=dependency[producer][consumer]
			B.append(-toAppend)
			paths=findAllPaths(producer,consumer,dependency)
			maxLen=0
			for path in paths:
				pathLength=0
				for k in range(1,len(path)):
					pathLength+=dependency[path[k-1]][path[k]]
				if(pathLength>maxLen):
					maxLen=pathLength
			if(maxLen>objLen):
				toKeep=consumer
		for key in C.keys():
			if(key==producer):
				C[key].append(-1)
			elif(key==toKeep):
				C[key].append(1)
			else:
				C[key].append(0)


def generatorMain(File,width=1920,sram=2,combine=False):
	"""
	docstring
	"""
	front_end.parser(File)
	cleanAST()
	A,C,dependency,stencils,pad=genDependency(width)
	print("=======================dependency=========================")
	pprint(dependency)
	virtStage = {}
	if (combine==True):
		stencils,dependency,pad,virtStage=combineLines(stencils,dependency,pad,width,A,C)
	B=[]
	readRegs={}
	print("============================================================")
	if (combine==True):
		# print(virtStage)
		accessLevels=genHardwareConstraints(dependency,stencils,pad,sram,A,B,width,readRegs,combine=combine,virtStage=virtStage)
	else:
		accessLevels=genHardwareConstraints(dependency,stencils,pad,sram,A,B,width,readRegs)
	# print(accessLevels)
	# print(A)
	genCausalityConstraints(dependency,A,B,C)
	print("================A=================")
	print(A)
	print("================C=================")
	print(C)
	pprint(virtStage)
	A_ub=[]
	C_ub=[]
	for i in A.keys():
		A_ub.append(A[i])
		C_ub.append(sum(C[i]))
	A_ub=np.asarray(A_ub)
	A_ub=A_ub.transpose()
	A_ub=-1*A_ub
	C_ub=np.asarray(C_ub)
	B_ub=np.asarray(B)
	variable=list(A.keys())
	return A_ub,B_ub,C_ub,variable,dependency,stencils,pad,readRegs,accessLevels,virtStage


if __name__=="__main__":
	File=open(sys.argv[1],'r')
	generatorMain(File)
	print("================================================")
	for node in AST.head.keys():
		print(f"Node: {node}")
		print(f"Producers: {AST.head[node].producers}")
		print(f"Coefs: {AST.head[node].coefficient}")