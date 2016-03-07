from __future__ import absolute_import
from __future__ import print_function
import sys
import glob

import time
import numpy as np
import pandas as pd
import os.path
from keras.preprocessing import sequence
from keras.optimizers import SGD, RMSprop, Adagrad
from keras.utils import np_utils
from keras.models import Sequential, Graph
from keras.layers.core import Dense, Dropout, Activation, TimeDistributedDense, Flatten, Reshape, Permute, Merge, LambdaMerge, Lambda
from keras.layers.convolutional import Convolution1D, MaxPooling1D, Convolution2D, MaxPooling2D, UpSampling1D, UpSampling2D
from keras.layers.advanced_activations import ParametricSoftplus
from keras.callbacks import ModelCheckpoint, Callback
import matplotlib.pyplot as plt


def draw_model(model):
    from IPython.display import SVG
    from keras.utils.visualize_util import to_graph
    from keras.utils.visualize_util import plot

    SVG(to_graph(model).create(prog='dot', format='svg'))
    plot(model, to_file='UFCNN/UFCNN_1.png')


def print_nodes_shapes(model):
    for k, v in model.inputs.items():
        print("{} : {} : {} : {}".format(k, type(v), v.input_shape, v.output_shape))
        
    for k, v in model.nodes.items():
        print("{} : {} : {} : {}".format(k, type(v), v.input_shape, v.output_shape))
        
    for k, v in model.outputs.items():
        print("{} : {} : {} : {}".format(k, type(v), v.input_shape, v.output_shape))

def save_neuralnet (model, model_name):

    json_string = model.to_json()
    open(model_name + '_architecture.json', 'w').write(json_string)
    model.save_weights(model_name + '_weights.h5', overwrite=True)

    yaml_string = model.to_yaml()
    with open(model_name + '_data.yml', 'w') as outfile:
        outfile.write( yaml_string)

        

def ufcnn_model(sequence_length=5000,
                           features=1,
                           nb_filter=150,
                           filter_length=5,
                           output_dim=1,
                           optimizer='adagrad',
                           loss='mse',
                           regression = True,
                           class_mode=None,
                           init="glorot_uniform"):
    

    model = Graph()
    model.add_input(name='input', input_shape=(sequence_length, features))
    #########################################################
    model.add_node(Convolution1D(nb_filter=nb_filter, filter_length=filter_length, border_mode='same', init=init), name='conv1', input='input')
    model.add_node(ParametricSoftplus(), name='relu1', input='conv1')
    #########################################################
    model.add_node(Convolution1D(nb_filter=nb_filter, filter_length=filter_length, border_mode='same', init=init), name='conv2', input='relu1')
    model.add_node(ParametricSoftplus(), name='relu2', input='conv2')
    #########################################################
    model.add_node(Convolution1D(nb_filter=nb_filter, filter_length=filter_length, border_mode='same', init=init), name='conv3', input='relu2')
    model.add_node(ParametricSoftplus(), name='relu3', input='conv3')
    #########################################################
    model.add_node(Convolution1D(nb_filter=nb_filter, filter_length=filter_length, border_mode='same', init=init), name='conv4', input='relu3')
    model.add_node(ParametricSoftplus(), name='relu4', input='conv4')
    #########################################################
    model.add_node(Convolution1D(nb_filter=nb_filter,filter_length=filter_length, border_mode='same', init=init),
                     name='conv5',
                     inputs=['relu2', 'relu4'],
                     merge_mode='sum')
    model.add_node(ParametricSoftplus(), name='relu5', input='conv5')
    #########################################################
    model.add_node(Convolution1D(nb_filter=nb_filter,filter_length=filter_length, border_mode='same', init=init),
                     name='conv6',
                     inputs=['relu1', 'relu5'],
                     merge_mode='sum')
    model.add_node(ParametricSoftplus(), name='relu6', input='conv6')
    #########################################################
    if regression:
        #########################################################
        model.add_node(Convolution1D(nb_filter=output_dim, filter_length=filter_length, border_mode='same', init=init), name='conv7', input='relu6')
        model.add_node(ParametricSoftplus(), name='relu7', input='conv7')
        model.add_output(name='output', input='conv7')
    else:
        model.add_node(Convolution1D(nb_filter=nb_filter, filter_length=filter_length, border_mode='same', init=init), name='conv7', input='relu6')
        model.add_node(ParametricSoftplus(), name='relu7', input='conv7')
        model.add_node(Flatten(), name='flatten', input='relu7')
        model.add_node(Dense(output_dim=output_dim, activation='softmax'), name='dense', input='flatten')
        model.add_output(name='output', input='dense')
    
    model.compile(optimizer=optimizer, loss={'output': loss})
    
    return model


def gen_cosine_amp(amp=100, period=25, x0=0, xn=50000, step=1, k=0.0001):
    """Generates an absolute cosine time series with the amplitude
    exponentially decreasing
    Arguments:
        amp: amplitude of the cosine function
        period: period of the cosine function
        x0: initial x of the time series
        xn: final x of the time series
        step: step of the time series discretization
        k: exponential rate
	Ernst 20160301 from https://github.com/fchollet/keras/blob/master/examples/stateful_lstm.py
        as a first test for the ufcnn
    """
    
    cos = np.zeros(((xn - x0) * step,  1, 1))
    print("Cos. Shape",cos.shape)
    for i in range(len(cos)):
        idx = x0 + i * step
        cos[i, 0, 0] = amp * np.cos(idx / (2 * np.pi * period))
        cos[i, 0, 0] = cos[i, 0, 0] * np.exp(-k * idx)
    return cos


def train_and_predict_regression(model, sequence_length=5000, batch_size=128, epochs=5):
    lahead = 1

    cos = gen_cosine_amp(xn = sequence_length * 100)

    expected_output = np.zeros((len(cos), 1, 1))

    for i in range(len(cos) - lahead):
        expected_output[i, 0] = np.mean(cos[i + 1:i + lahead + 1])

    print('Training')
    for i in range(epochs):
        print('Epoch', i, '/', epochs)
        model.fit({'input': cos, 'output': expected_output},
                  verbose=1,
                  nb_epoch=1,
                  shuffle=False,
                  batch_size=batch_size)

    print('Predicting')
    predicted_output = model.predict({'input': cos,}, batch_size=batch_size)
    
    return {'model': model, 'predicted_output': predicted_output, 'expected_output': expected_output}



def prepare_tradcom_classification(training = True, sequence_length = 5000, features = 32, output_dim = 3, filename = 'prod_data_20130729v.txt'):
    """
    prepare the datasets for the trading competition. training determines which datasets will be red
    """

    day_file = filename
    sig_file = filename.replace('prod_data','signal')
    sig_file = sig_file.replace('txt','csv')

    print("Working on files: ",day_file, ", ",sig_file)

    if not os.path.isfile(sig_file):
        print("File ",sig_file," is not existing. Aborting.")
        sys.exit()


    Xdf = pd.read_csv(day_file, sep=" ", index_col = 0, header = None,)
    ydf = pd.read_csv(sig_file, index_col = 0, names = ['signal',], )

    # subtract the mean rom all rows
    Xdf = Xdf.sub(Xdf.mean())

    Xdf = Xdf.div(Xdf.std())

    #print("X-Dataframe after standardization")
    #print(Xdf)
    #print("Input check")
    #print("Mean (should be 0)")
    #print (Xdf.mean())
    #print("Variance (should be 1)")
    #print (Xdf.std())

    Xdf_array = Xdf.values
    
    X_xdim, X_ydim = Xdf_array.shape

    X = np.zeros((X_xdim, sequence_length, X_ydim))
    start_time = time.time()

    for i in range (X_xdim):
        for s in range(sequence_length):
            s_i = i- sequence_length + s + 1
            #      0   5000              4999
            #   5001   5000         
            if s_i >= 0: 
                for j in range (X_ydim):
                    X[s_i][s][j] = Xdf_array[i][j]

    #print("Time for Array Fill ", time.time()-start_time)  

    ydf['sell'] = ydf.apply(lambda row: (1 if row['signal'] < -0.9 else 0 ), axis=1)
    ydf['buy']  = ydf.apply(lambda row: (1 if row['signal'] > 0.9 else 0 ), axis=1)
    ydf['hold'] = ydf.apply(lambda row: (1 if row['buy'] < 0.9 and row['sell'] <  0.9 else 0 ), axis=1)

    del ydf['signal']
    y = ydf.values

    return (X,y)



def train_and_predict_classification(model, sequence_length=5000, features=32, output_dim=3, batch_size=128, epochs=5, name = "model",  training_count=3, testing_count=3):

    final_loss = 0
    file_list = sorted(glob.glob('./training_data_large/prod_data_*v.txt'))

    if len(file_list) == 0:
        print ("Files ./training_data_large/product_data_*txt and signal_*.csv are needed. Please copy them in the ./training_data_large/ . Aborting.")
        sys.exit()
 
    line = np.zeros((epochs * training_count,))

    for j in range(training_count):
        filename = file_list[j]
        print('Training: ',filename)

        X,y = prepare_tradcom_classification(training = True, sequence_length = sequence_length, features = features, output_dim = output_dim, filename = filename)

        for i in range(epochs):
            print('File: ',j,', Epoch: ', i, '/', epochs)
            history = model.fit({'input': X, 'output': y},
                      verbose=2,
                      nb_epoch=1,
                      shuffle=False,
                      batch_size=batch_size)
            print(history.history)
            sys.stdout.flush()
            final_loss = history.history['loss']
            line[j*training_count+i] = final_loss[0]

        save_neuralnet (model, "ufcnn_"+str(j))
    
    plt.figure()
    plt.plot(line) 
    plt.savefig("Convergence.png")
    #plt.show()


    for k in range(testing_count):
        filename = file_list[training_count + k]
        print("Predicting: ",filename)

        X,y = prepare_tradcom_classification(training = True, sequence_length = sequence_length, features = features, output_dim = output_dim, filename = filename )
        predicted_output = model.predict({'input': X,}, batch_size=batch_size, verbose = 2)
        #print(predicted_output)

        yp = predicted_output['output']
        xdim, ydim = yp.shape
    
        ## MSE for testing
        total_error  = 0
        correct_class= 0
        for i in range (xdim):
            delta = 0.
            for j in range(ydim):
                delta += (y[i][j] - yp[i][j]) * (y[i][j] - yp[i][j])
                #print ("Row %d, MSError: %8.5f " % (i, delta/ydim))

            total_error += delta
            if np.argmax(y[i]) == np.argmax(yp[i]):
                correct_class += 1

        print ("FIN Correct Class Assignment:  %6d /%7d" % (correct_class, xdim))
        print ("FIN Final Loss:  ", final_loss)
    
    return {'model': model, 'predicted_output': predicted_output['output'], 'expected_output': y}


#########################################################
## Test the net with damped cosine  / remove later...
#########################################################


if len(sys.argv) < 2 :
    print ("Usage: UFCNN1.py action    with action from [cos_small, cos, tradcom]")
    sys.exit()

action = sys.argv[1]


sequence_length = 64        # same as in Roni Mittelman's paper - this is 2 times 32 - a line in Ronis input contains 33 numbers, but 1 is time and is omitted
features = 1                # guess changed Ernst 20160301
nb_filter = 150             # same as in Roni Mittelman's paper
filter_length = 5           # same as in Roni Mittelman's paper
output_dim = 1              # guess changed Ernst 20160301

if action == 'cos_small':
    print("Running model: ", action)
    UFCNN_1 = ufcnn_model(sequence_length=sequence_length)
    print_nodes_shapes(UFCNN_1)
    case_1 = train_and_predict_regression(UFCNN_1, sequence_length=sequence_length)

    print('Ploting Results')
    plt.figure(figsize=(18,3))
    plt.plot(case_1['expected_output'].reshape(-1)[-10000:]) #, predicted_output['output'].reshape(-1))
    plt.plot(case_1['predicted_output']['output'].reshape(-1)[-10000:])
    #plt.savefig('sinus.png')
    plt.show()


if action == 'cos':
    print("Running model: ", action)
    UFCNN_2 = ufcnn_model()
    print_nodes_shapes(UFCNN_2)
    case_2 = train_and_predict_regression(UFCNN_2)

    print('Ploting Results')
    plt.figure(figsize=(18,3))
    plt.plot(case_2['expected_output'].reshape(-1)[-10000:]) #, predicted_output['output'].reshape(-1))
    plt.plot(case_2['predicted_output']['output'].reshape(-1)[-10000:])
    #plt.savefig('sinus.png')
    plt.show()

if action == 'tradcom':
    print("Running model: ", action)
    sequence_length = 50
    features = 32
    output_dim = 3

    UFCNN_TC = ufcnn_model(regression = False, output_dim=output_dim, features=features, 
       loss="categorical_crossentropy", sequence_length=sequence_length, optimizer="sgd" )
    #print_nodes_shapes(UFCNN_TC)
    case_tc = train_and_predict_classification(UFCNN_TC, features=features, output_dim=output_dim, sequence_length=sequence_length, epochs=150, training_count=30, testing_count = 120)
  
