import sys
import os
import argparse
import json

from sklearn.model_selection import train_test_split

from core.data.data_loader import *
from core.models.lstm import ModelLSTM, ModelLSTMParalel
from core.utils.metrics import *
from core.utils.utils import *

import numpy as np

def parse_args():
    """Parse arguments."""
    # Parameters settings
    parser = argparse.ArgumentParser(description="LSTM implementation ")

    # Dataset setting
    parser.add_argument('--data_prefix', type=str, default="./dataset/2020_100_sorted.csv", help='Data file')
    parser.add_argument('--save_model', type=str, default="./results/model_lstm.h5", help='Model for inference')

    # Training parameters setting
    parser.add_argument('--neurons', type=int, default=1000, help='number of epochs to train [10, 200, 500]')
    parser.add_argument('--batch_size', type=int, default=1, help='number of batch')
    
    parser.add_argument('--epochs', type=int, default=15, help='number of epochs to train [10, 200, 500]')
    parser.add_argument('--lr', type=float, default=0.001, help='learning rate [0.001] reduced by 0.1 after each 10000 iterations')

    # parse the arguments
    args = parser.parse_args()

    return args

def gpu():
    import tensorflow as tf
    from tensorflow import set_random_seed

    import keras.backend as K
    from keras.backend.tensorflow_backend import set_session
    
    #configure  gpu_options.allow_growth = True in order to CuDNNLSTM layer work on RTX
    config = tf.ConfigProto(device_count = {'GPU': 0})
    config.gpu_options.allow_growth = True
    sess = tf.Session(config=config)
    set_session(sess)

    set_random_seed(1)

def no_gpu():
    import os
    os.environ["CUDA_VISIBLE_DEVICES"]="-1"
    import tensorflow as tf

    config=tf.ConfigProto(log_device_placement=True)
    sess = tf.Session(config=config)
    set_session(sess)

def main():

    args = parse_args()       
    
    gpu()

    # create defaults dirs
    output_path = 'results/'
    output_logs = 'logs/'

    if os.path.isdir(output_path) == False:
        os.mkdir(output_path)

    if os.path.isdir(output_logs) == False:
        os.mkdir(output_logs)        

    neurons = args.neurons
    batch_size = args.batch_size
    epochs = args.epochs

    # load configurations of model and others
    configs = json.load(open('config-paralel.json', 'r'))

    save_dir = configs['model']['save_dir']
    data_dir = configs['data']['filename']

    save_fname = os.path.join(save_dir, 'architecture-%s.png' % configs['model']['name'])
    save_fnameh5 = os.path.join(save_dir, 'model-%s.h5' % configs['model']['name'])
    
    time_steps =  configs['model']['layers'][0]['input_timesteps']  # the number of points or hits
    num_features = configs['model']['layers'][0]['input_features']  # the number of features of each hits

    split = configs['data']['train_split']  # the number of features of each hits
    
    # prepare data set
    data = Dataset(data_dir, KindNormalization.Zscore)

    X, X_, y = data.prepare_training_data(FeatureType.Divided, normalise=True,
                                                  cilyndrical=False)

    # reshape data     
    X = data.reshape3d(X, time_steps, num_features)
    X_ = data.reshape3d(X_, time_steps, 1)

    X_train, X_test, X_train_, X_test_, y_train, y_test = train_test_split(X, X_, y, test_size=1-split, random_state=42)
    
    print('[Data] shape data X_train.shape:', X_train.shape)
    print('[Data] shape data X_test.shape:', X_test.shape)
    print('[Data] shape data y_train.shape:', y_train.shape)
    print('[Data] shape data y_test.shape:', y_test.shape)


    model = ModelLSTMParalel()
    
    model.build_model(configs)
    model.save_architecture(save_fname)

    x_train = [X_train, X_train_]

    # in-memory training
    history = model.train(
        x=x_train,
        y=y_train,
        epochs = configs['training']['epochs'],
        batch_size = configs['training']['batch_size'],
        save_fname = save_fnameh5
    )

    #model.evaluate([X_test, X_test_], y_test)
    evaluate_training(history, output_path)

    x_test = [X_test, X_test_]
    
    predicted = model.predict_one_hit(x_test)

    y_predicted = np.reshape(predicted, (predicted.shape[0]*predicted.shape[1], 1))
    y_true_ = data.reshape2d(y_test, 1)

    # calculing scores
    result = calc_score(y_true_, y_predicted, report=True)
    r2, rmse, rmses = evaluate_forecast(y_test, predicted)
    summarize_scores(r2, rmse,rmses)


    print('[Data] shape y_test ', y_test.shape)
    print('[Data] shape predicted ', predicted.shape)

    print('[Data] shape y_test ', y_test.shape)
    print('[Data] shape predicted ', predicted.shape)

    print('[Output] Finding shortest points ... ')
    near_points = get_shortest_points(y_test, predicted)
    y_near_points = pd.DataFrame(near_points)

    print('[Data] shape predicted ', y_near_points.shape)

    # we need to transform to original data
    y_test_orig = data.inverse_transform(y_test)
    y_predicted_orig = data.inverse_transform(predicted)
    y_near_orig = data.inverse_transform(y_near_points)

    print(y_test_orig.shape)
    print(y_predicted_orig.shape)

    print('[Output] Calculating distances ...')

    dist0 = calculate_distances_matrix(y_predicted_orig, y_test_orig)
    dist1 = calculate_distances_matrix(y_predicted_orig, y_near_orig)

    print('[Output] Saving distances ... ')
    save_fname = os.path.join(save_dir, 'distances.png' )
    plot_distances(dist0, dist1, save_fname)

    #Save data to plot
    X, X_, y = data.prepare_training_data(FeatureType.Divided, normalise=False,
                                                      cilyndrical=False)
    X_train, X_test, X_train_, X_test_, y_train, y_test = train_test_split(X, X_, y,
                                                                           test_size=1-split, random_state=42)

    y_pred = pd.DataFrame(y_predicted_orig)
    y_true = pd.DataFrame(y_test_orig)

    print('[Output] saving results ...')
    y_true.to_csv('y_true.csv', header=False, index=False)
    y_pred.to_csv('y_pred.csv', header=False, index=False)
    X_test.to_csv('x_test.csv', header=False, index=False)

if __name__=='__main__':
    main()









